"""Message repository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import Message


class MessageRepository:
    def list_by_booking(self, db: Session, booking_id: UUID) -> list[Message]:
        stmt = select(Message).where(Message.booking_id == booking_id).order_by(Message.created_at)
        return list(db.execute(stmt).scalars().all())

    def create(self, db: Session, message: Message) -> Message:
        db.add(message)
        db.flush()
        return message
