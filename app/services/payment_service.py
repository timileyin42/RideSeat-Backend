"""Payment service."""

import logging
import stripe
import time
from datetime import timedelta
from threading import Lock
from sqlalchemy.orm import Session
from uuid import UUID

import redis

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

logger = logging.getLogger(__name__)

_WEBHOOK_DEDUP_TTL = 86_400  # 24 hours — matches Stripe's retry window
_WEBHOOK_KEY = "rideway:stripe_event:{}"


def _redis_client() -> redis.Redis:
    settings = get_settings()
    base_url = settings.celery_broker_url.rsplit("/", 1)[0]
    return redis.from_url(f"{base_url}/3", decode_responses=True)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_seconds: int = 60) -> None:
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

    def _configured_stripe(self) -> None:
        settings = get_settings()
        if not settings.stripe_secret_key:
            raise ValueError("Payments are not yet enabled")
        if not payment_circuit_breaker.allow():
            raise ValueError("Payment service temporarily unavailable, try again shortly")
        stripe.api_key = settings.stripe_secret_key
        stripe.max_network_retries = 2
        # Set timeout — stripe 12+ uses http_client, older versions used stripe.timeout
        try:
            stripe.default_http_client = stripe.new_default_http_client(timeout=30)
        except Exception:
            pass

    def create_payment_intent(self, db: Session, booking_id: UUID, actor_id: UUID) -> Payment:
        """Create a Stripe PaymentIntent synchronously and return client_secret immediately."""
        self._configured_stripe()
        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking:
            raise ValueError("Booking not found")
        if booking.passenger_id != actor_id:
            raise ValueError("Not allowed to pay for this booking")

        existing = self.payment_repo.get_by_booking(db, booking_id)
        if existing:
            if existing.stripe_client_secret:
                return existing
            return self._sync_stripe_intent(db, existing)

        amount = float(booking.total_amount)
        platform_fee = round(amount * PLATFORM_FEE_PERCENT, 2)
        payout = round(amount - platform_fee, 2)
        payment = Payment(
            booking_id=booking_id,
            amount=amount,
            platform_fee=platform_fee,
            payout_amount=payout,
            status=PaymentStatus.REQUIRES_PAYMENT_METHOD,
        )
        saved = self.payment_repo.create(db, payment)
        return self._sync_stripe_intent(db, saved)

    def _sync_stripe_intent(self, db: Session, payment: Payment) -> Payment:
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(float(payment.amount) * 100),
                currency=CURRENCY,
                metadata={"booking_id": str(payment.booking_id)},
                idempotency_key=f"payment_intent:{payment.id}",
            )
            payment.stripe_payment_intent_id = intent.id
            payment.stripe_client_secret = intent.client_secret
            payment.status = PaymentStatus.REQUIRES_PAYMENT_METHOD
            self.payment_repo.update(db, payment)
            payment_circuit_breaker.record_success()
            return payment
        except stripe.StripeError as exc:
            payment_circuit_breaker.record_failure()
            raise ValueError(f"Stripe error: {exc.user_message or str(exc)}") from exc

    def process_payment_intent(self, payment_id: UUID) -> None:
        """Celery recovery: fill in missing PI for payments created before a Stripe outage."""
        db = create_db_session()
        try:
            payment = self.payment_repo.get_by_id(db, payment_id)
            if not payment or payment.stripe_payment_intent_id:
                return
            if not payment_circuit_breaker.allow():
                return
            settings = get_settings()
            if not settings.stripe_secret_key:
                return
            stripe.api_key = settings.stripe_secret_key
            self._sync_stripe_intent(db, payment)
            db.commit()
        except Exception:
            db.rollback()
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
            raise ValueError("Driver has not connected their payout account")
        self._configured_stripe()
        try:
            transfer = stripe.Transfer.create(
                amount=int(float(payment.payout_amount) * 100),
                currency=CURRENCY,
                destination=driver.payment_details,
                metadata={"booking_id": str(booking_id)},
                idempotency_key=f"payout:{booking_id}",
            )
            payment_circuit_breaker.record_success()
        except stripe.StripeError as exc:
            payment_circuit_breaker.record_failure()
            raise ValueError(f"Payout failed: {exc.user_message or str(exc)}") from exc
        payment.stripe_transfer_id = transfer.id
        return self.payment_repo.update(db, payment)

    def handle_webhook(self, db: Session, payload: bytes, sig_header: str) -> Payment:
        settings = get_settings()
        if not settings.stripe_webhook_secret:
            raise ValueError("Payments are not yet enabled")
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
        except stripe.SignatureVerificationError as exc:
            raise ValueError("Invalid webhook signature") from exc

        # Deduplicate: Stripe delivers at-least-once; same event_id within 24h is a replay
        event_id = event["id"]
        try:
            r = _redis_client()
            key = _WEBHOOK_KEY.format(event_id)
            already_processed = not r.set(key, "1", nx=True, ex=_WEBHOOK_DEDUP_TTL)
            if already_processed:
                logger.info("Duplicate Stripe webhook ignored", extra={"event_id": event_id})
                raise ValueError(f"Duplicate event: {event_id}")
        except redis.RedisError:
            # Redis unavailable — log and continue; better to double-process than to drop
            logger.warning("Redis unavailable for webhook dedup, processing anyway", extra={"event_id": event_id})

        event_type = event["type"]
        data_object = event["data"]["object"]

        if event_type not in (
            "payment_intent.succeeded",
            "payment_intent.processing",
            "payment_intent.payment_failed",
            "payment_intent.canceled",
        ):
            raise ValueError(f"Unhandled event type: {event_type}")

        booking_id_str = (data_object.get("metadata") or {}).get("booking_id")
        if not booking_id_str:
            raise ValueError("No booking_id in webhook metadata")

        booking_id = UUID(booking_id_str)
        payment = self.payment_repo.get_by_booking(db, booking_id)
        if not payment:
            raise ValueError("Payment not found")

        if event_type == "payment_intent.succeeded":
            payment.status = PaymentStatus.SUCCEEDED
            payment.stripe_charge_id = data_object.get("latest_charge")
            self.trigger_payout_background(booking_id)
        elif event_type == "payment_intent.processing":
            payment.status = PaymentStatus.PROCESSING
        else:
            payment.status = PaymentStatus.FAILED

        return self.payment_repo.update(db, payment)

    # --- Stripe Connect Custom (driver payout onboarding) ---

    def create_connect_account(self, db: Session, driver_id: UUID, data: dict, client_ip: str) -> dict:
        """
        Create a Stripe Custom Connect account for a driver in one call.
        Collects personal details, bank account, and ToS acceptance — no redirect needed.
        """
        if not data.get("tos_accepted"):
            raise ValueError("Driver must accept Stripe's Terms of Service")

        self._configured_stripe()
        driver = self.user_repo.get_by_id(db, driver_id)
        if not driver:
            raise ValueError("User not found")

        import time as _time
        try:
            if driver.payment_details:
                account_id = driver.payment_details
            else:
                account = stripe.Account.create(
                    type="custom",
                    country="GB",
                    email=driver.email,
                    business_type="individual",
                    capabilities={"transfers": {"requested": True}},
                    individual={
                        "first_name": data["first_name"],
                        "last_name": data["last_name"],
                        "dob": {
                            "day": data["dob"]["day"],
                            "month": data["dob"]["month"],
                            "year": data["dob"]["year"],
                        },
                        "address": {
                            "line1": data["address"]["line1"],
                            "city": data["address"]["city"],
                            "postal_code": data["address"]["postal_code"],
                            "country": "GB",
                        },
                        "email": driver.email,
                        "phone": data["phone"],
                    },
                    tos_acceptance={
                        "date": int(_time.time()),
                        "ip": client_ip,
                    },
                    metadata={"user_id": str(driver_id)},
                )
                account_id = account.id
                driver.payment_details = account_id
                self.user_repo.update(db, driver)

            # Attach UK bank account for payouts
            stripe.Account.create_external_account(
                account_id,
                external_account={
                    "object": "bank_account",
                    "country": "GB",
                    "currency": "gbp",
                    "account_holder_name": data["account_holder_name"],
                    "routing_number": data["sort_code"],
                    "account_number": data["account_number"],
                },
                idempotency_key=f"bank:{driver_id}",
            )

            account = stripe.Account.retrieve(account_id)
            payment_circuit_breaker.record_success()
        except stripe.StripeError as exc:
            payment_circuit_breaker.record_failure()
            raise ValueError(f"Stripe error: {exc.user_message or str(exc)}") from exc

        return {
            "account_id": account_id,
            "charges_enabled": account.get("charges_enabled", False),
            "payouts_enabled": account.get("payouts_enabled", False),
        }

    def upload_identity_document(self, driver_id: UUID, file_bytes: bytes, filename: str, purpose: str) -> dict:
        """
        Upload a front/back ID document to Stripe and attach it to the driver's account.
        purpose: 'identity_document_front' | 'identity_document_back'
        """
        self._configured_stripe()
        import io
        import re
        safe_filename = re.sub(r"[^\w.\-]", "_", filename or "document.jpg")
        ext = safe_filename.rsplit(".", 1)[-1].lower()
        mime = "image/png" if ext == "png" else "image/jpeg"
        try:
            stripe_file = stripe.File.create(
                purpose="identity_document",
                file=io.BytesIO(file_bytes),
                file_options={"filename": safe_filename, "content_type": mime},
            )
            payment_circuit_breaker.record_success()
        except stripe.StripeError as exc:
            payment_circuit_breaker.record_failure()
            raise ValueError(f"Stripe error: {exc.user_message or str(exc)}") from exc
        return {"file_id": stripe_file.id, "message": f"{purpose} uploaded successfully"}

    def attach_identity_document(self, db: Session, driver_id: UUID, front_file_id: str, back_file_id: str | None) -> None:
        """Attach uploaded document file IDs to the driver's Stripe account."""
        self._configured_stripe()
        driver = self.user_repo.get_by_id(db, driver_id)
        if not driver or not driver.payment_details:
            raise ValueError("Driver has no connected account")
        doc: dict = {"front": front_file_id}
        if back_file_id:
            doc["back"] = back_file_id
        try:
            stripe.Account.modify(
                driver.payment_details,
                individual={"verification": {"document": doc}},
            )
            payment_circuit_breaker.record_success()
        except stripe.StripeError as exc:
            payment_circuit_breaker.record_failure()
            raise ValueError(f"Stripe error: {exc.user_message or str(exc)}") from exc

    def request_payout(self, db: Session, driver_id: UUID) -> dict:
        """Driver manually requests payout for all completed, unpaid earnings."""
        self._configured_stripe()
        driver = self.user_repo.get_by_id(db, driver_id)
        if not driver:
            raise ValueError("User not found")
        if not driver.payment_details:
            raise ValueError("You must set up your payout account before requesting a payout")

        pending = self.payment_repo.list_unpaid_by_driver(db, driver_id)
        if not pending:
            return {"transfers_initiated": 0, "total_amount": 0.0, "message": "No pending earnings to pay out"}

        total = 0.0
        count = 0
        errors = []
        for payment in pending:
            try:
                self.create_payout_for_booking(db, payment.booking_id)
                total += float(payment.payout_amount)
                count += 1
            except ValueError as exc:
                errors.append(str(exc))

        return {
            "transfers_initiated": count,
            "total_amount": round(total, 2),
            "message": f"{count} payout(s) initiated" + (f"; {len(errors)} skipped" if errors else ""),
        }

    def get_connect_status(self, db: Session, driver_id: UUID) -> dict:
        """Return Stripe Connect onboarding status for the driver."""
        self._configured_stripe()
        driver = self.user_repo.get_by_id(db, driver_id)
        if not driver:
            raise ValueError("User not found")
        if not driver.payment_details:
            return {"connected": False, "charges_enabled": False, "payouts_enabled": False, "account_id": None}
        try:
            account = stripe.Account.retrieve(driver.payment_details)
            payment_circuit_breaker.record_success()
        except stripe.StripeError as exc:
            payment_circuit_breaker.record_failure()
            raise ValueError(f"Stripe error: {exc.user_message or str(exc)}") from exc
        return {
            "connected": account.get("charges_enabled", False),
            "charges_enabled": account.get("charges_enabled", False),
            "payouts_enabled": account.get("payouts_enabled", False),
            "account_id": driver.payment_details,
        }
