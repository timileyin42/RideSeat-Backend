"""Payment repository."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import PaymentStatus
from app.models.payment import Payment


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
