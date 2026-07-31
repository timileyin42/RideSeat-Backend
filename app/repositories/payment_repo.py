"""Payment repository."""

from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy import cast, Date, func, select
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

    def list_all(
        self,
        db: Session,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[Payment]:
        stmt = select(Payment)
        if status:
            stmt = stmt.where(Payment.status == status)
        stmt = stmt.order_by(Payment.created_at.desc()).offset(offset).limit(limit)
        return list(db.execute(stmt).scalars().all())

    def revenue_timeseries(self, db: Session, days: int = 7) -> list[dict]:
        """Daily revenue for the last N days."""
        from app.utils.datetime import now_utc
        since = now_utc() - timedelta(days=days)
        stmt = (
            select(
                cast(Payment.created_at, Date).label("date"),
                func.coalesce(func.sum(Payment.amount), 0).label("value"),
            )
            .where(Payment.status == PaymentStatus.SUCCEEDED, Payment.created_at >= since)
            .group_by(cast(Payment.created_at, Date))
            .order_by(cast(Payment.created_at, Date))
        )
        rows = db.execute(stmt).all()
        return [{"date": str(row.date), "value": float(row.value)} for row in rows]

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

    def sum_total_revenue(self, db: Session, since=None) -> float:
        stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == PaymentStatus.SUCCEEDED)
        if since is not None:
            stmt = stmt.where(Payment.created_at >= since)
        return float(db.execute(stmt).scalar_one())

    def sum_platform_fees(self, db: Session, since=None) -> float:
        stmt = select(func.coalesce(func.sum(Payment.platform_fee), 0)).where(Payment.status == PaymentStatus.SUCCEEDED)
        if since is not None:
            stmt = stmt.where(Payment.created_at >= since)
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
