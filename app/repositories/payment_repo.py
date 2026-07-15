"""Payment repository."""

from uuid import UUID
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import PaymentStatus
from app.models.payment import Payment
from app.models.booking import Booking
from app.models.trip import Trip


class PaymentRepository:
    def get_by_id(self, db: Session, payment_id: UUID) -> Payment | None:
        return db.get(Payment, payment_id)

    def get_by_booking(self, db: Session, booking_id: UUID) -> Payment | None:
        stmt = select(Payment).where(Payment.booking_id == booking_id)
        return db.execute(stmt).scalar_one_or_none()

    def create(self, db: Session, payment: Payment) -> Payment:
        db.add(payment)
        db.flush()
        return payment

    def update(self, db: Session, payment: Payment) -> Payment:
        db.add(payment)
        db.flush()
        return payment

    def list_pending_intents(self, db: Session, limit: int = 50) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(
                Payment.stripe_payment_intent_id.is_(None),
                Payment.status == PaymentStatus.REQUIRES_PAYMENT_METHOD,
            )
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def sum_total_revenue(self, db: Session) -> float:
        stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == PaymentStatus.SUCCEEDED)
        return float(db.execute(stmt).scalar_one())

    def sum_platform_fees(self, db: Session) -> float:
        stmt = select(func.coalesce(func.sum(Payment.platform_fee), 0)).where(Payment.status == PaymentStatus.SUCCEEDED)
        return float(db.execute(stmt).scalar_one())

    def list_payouts_by_driver(self, db: Session, driver_id: UUID) -> list[Payment]:
        """All payments for trips driven by this driver, ordered newest first."""
        stmt = (
            select(Payment)
            .join(Booking, Booking.id == Payment.booking_id)
            .join(Trip, Trip.id == Booking.trip_id)
            .where(Trip.driver_id == driver_id)
            .order_by(Payment.created_at.desc())
        )
        return list(db.execute(stmt).scalars().all())

    def list_unpaid_by_driver(self, db: Session, driver_id: UUID) -> list[Payment]:
        """Payments that succeeded but haven't been transferred to the driver yet."""
        stmt = (
            select(Payment)
            .join(Booking, Booking.id == Payment.booking_id)
            .join(Trip, Trip.id == Booking.trip_id)
            .where(
                Trip.driver_id == driver_id,
                Payment.status == PaymentStatus.SUCCEEDED,
                Payment.stripe_transfer_id.is_(None),
            )
        )
        return list(db.execute(stmt).scalars().all())

    def list_by_passenger_between(
        self,
        db: Session,
        passenger_id: UUID,
        start: datetime,
        end: datetime,
    ) -> list[Payment]:
        stmt = (
            select(Payment)
            .join(Booking, Booking.id == Payment.booking_id)
            .where(
                Booking.passenger_id == passenger_id,
                Payment.created_at >= start,
                Payment.created_at <= end,
                Payment.status == PaymentStatus.SUCCEEDED,
            )
            .order_by(Payment.created_at.desc())
        )
        return list(db.execute(stmt).scalars().all())
