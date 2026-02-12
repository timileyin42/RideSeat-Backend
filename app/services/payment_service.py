"""Payment service."""

import stripe
import time
from datetime import timedelta
from threading import Lock
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.config import get_settings
from app.core.celery_app import celery_app
from app.core.constants import CURRENCY, PLATFORM_FEE_PERCENT, PaymentStatus
from app.core.database import create_db_session
from app.models.payment import Payment
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.utils.datetime import now_utc


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_seconds: int = 30) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.failure_count = 0
        self.open_until = 0.0
        self.lock = Lock()

    def allow(self) -> bool:
        with self.lock:
            if self.open_until > time.monotonic():
                return False
            return True

    def record_success(self) -> None:
        with self.lock:
            self.failure_count = 0
            self.open_until = 0.0

    def record_failure(self) -> None:
        with self.lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.open_until = time.monotonic() + self.recovery_seconds


payment_circuit_breaker = CircuitBreaker()


class PaymentService:
    def __init__(
        self,
        payment_repo: PaymentRepository,
        booking_repo: BookingRepository,
        trip_repo: TripRepository,
        user_repo: UserRepository,
    ) -> None:
        self.payment_repo = payment_repo
        self.booking_repo = booking_repo
        self.trip_repo = trip_repo
        self.user_repo = user_repo

    def create_intent_background(self, db: Session, booking_id: UUID, actor_id: UUID, background_tasks) -> Payment:
        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking:
            raise ValueError("Booking not found")
        if booking.passenger_id != actor_id:
            raise ValueError("Not allowed to pay for this booking")
        existing = self.payment_repo.get_by_booking(db, booking_id)
        if existing:
            if existing.stripe_payment_intent_id is None:
                celery_app.send_task("app.tasks.payment_tasks.process_payment_intent", args=[str(existing.id)])
            return existing
        amount = float(booking.total_amount)
        platform_fee = round(amount * PLATFORM_FEE_PERCENT, 2)
        payout = round(amount - platform_fee, 2)
        payment = Payment(
            booking_id=booking_id,
            amount=amount,
            platform_fee=platform_fee,
            payout_amount=payout,
            status=PaymentStatus.REQUIRES_PAYMENT_METHOD,
            stripe_payment_intent_id=None,
        )
        saved = self.payment_repo.create(db, payment)
        celery_app.send_task("app.tasks.payment_tasks.process_payment_intent", args=[str(saved.id)])
        return saved

    def process_payment_intent(self, payment_id: UUID) -> None:
        db = create_db_session()
        try:
            payment = self.payment_repo.get_by_id(db, payment_id)
            if not payment or payment.stripe_payment_intent_id:
                return
            if not payment_circuit_breaker.allow():
                return
            settings = get_settings()
            stripe.api_key = settings.stripe_secret_key
            intent = stripe.PaymentIntent.create(
                amount=int(float(payment.amount) * 100),
                currency=CURRENCY,
                metadata={"booking_id": str(payment.booking_id)},
                idempotency_key=f"payment_intent:{payment.id}",
            )
            payment.stripe_payment_intent_id = intent.id
            payment.status = PaymentStatus.REQUIRES_PAYMENT_METHOD
            self.payment_repo.update(db, payment)
            db.commit()
            payment_circuit_breaker.record_success()
        except Exception:
            db.rollback()
            payment_circuit_breaker.record_failure()
        finally:
            db.close()

    def process_pending_intents(self, limit: int = 50) -> None:
        db = create_db_session()
        try:
            pending = self.payment_repo.list_pending_intents(db, limit=limit)
            for payment in pending:
                self.process_payment_intent(payment.id)
        finally:
            db.close()

    def trigger_payout_background(self, booking_id: UUID) -> None:
        celery_app.send_task("app.tasks.payment_tasks.process_payout", args=[str(booking_id)])

    def process_payout(self, booking_id: str | UUID) -> None:
        booking_uuid = UUID(booking_id) if isinstance(booking_id, str) else booking_id
        db = create_db_session()
        try:
            self.create_payout_for_booking(db, booking_uuid)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def get_payment_status_for_user(self, db: Session, booking_id: UUID, actor_id: UUID) -> Payment:
        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking:
            raise ValueError("Booking not found")
        trip = self.trip_repo.get_by_id(db, booking.trip_id)
        if not trip:
            raise ValueError("Trip not found")
        if actor_id not in {booking.passenger_id, trip.driver_id}:
            raise ValueError("Not allowed to view payment")
        payment = self.payment_repo.get_by_booking(db, booking_id)
        if not payment:
            raise ValueError("Payment not found")
        return payment

    def list_payment_history(self, db: Session, passenger_id: UUID, period: str) -> list[Payment]:
        now = now_utc()
        if period == "7d":
            start = now - timedelta(days=7)
        elif period == "30d":
            start = now - timedelta(days=30)
        elif period == "6m":
            start = now - timedelta(days=182)
        elif period == "1y":
            start = now - timedelta(days=365)
        else:
            raise ValueError("Invalid period")
        return self.payment_repo.list_by_passenger_between(db, passenger_id, start=start, end=now)

    def create_payout_for_booking(self, db: Session, booking_id: UUID) -> Payment:
        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking:
            raise ValueError("Booking not found")
        payment = self.payment_repo.get_by_booking(db, booking_id)
        if not payment:
            raise ValueError("Payment not found")
        if payment.status != PaymentStatus.SUCCEEDED:
            raise ValueError("Payment not completed")
        if payment.stripe_transfer_id:
            return payment
        trip = self.trip_repo.get_by_id(db, booking.trip_id)
        if not trip:
            raise ValueError("Trip not found")
        driver = self.user_repo.get_by_id(db, trip.driver_id)
        if not driver or not driver.payment_details:
            raise ValueError("Driver payment details missing")
        if not payment_circuit_breaker.allow():
            raise ValueError("Payment service unavailable")
        settings = get_settings()
        stripe.api_key = settings.stripe_secret_key
        try:
            transfer = stripe.Transfer.create(
                amount=int(float(payment.payout_amount) * 100),
                currency=CURRENCY,
                destination=driver.payment_details,
                metadata={"booking_id": str(booking_id)},
                idempotency_key=f"payout:{booking_id}",
            )
        except Exception as exc:
            payment_circuit_breaker.record_failure()
            raise ValueError("Payout failed") from exc
        payment.stripe_transfer_id = transfer.id
        updated = self.payment_repo.update(db, payment)
        payment_circuit_breaker.record_success()
        return updated

    def handle_webhook(self, db: Session, payload: bytes, sig_header: str) -> Payment:
        settings = get_settings()
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
        data_object = event["data"]["object"]
        if data_object.get("metadata") and "booking_id" in data_object["metadata"]:
            booking_id = UUID(data_object["metadata"]["booking_id"])
            payment = self.payment_repo.get_by_booking(db, booking_id)
            if not payment:
                raise ValueError("Payment not found")
            status = data_object.get("status", "").upper()
            if status == "SUCCEEDED":
                payment.status = PaymentStatus.SUCCEEDED
            elif status == "PROCESSING":
                payment.status = PaymentStatus.PROCESSING
            else:
                payment.status = PaymentStatus.FAILED
            payment.stripe_charge_id = data_object.get("latest_charge")
            return self.payment_repo.update(db, payment)
        raise ValueError("Invalid webhook payload")
