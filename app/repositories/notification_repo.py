"""Notification repository."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationRepository:
    def get_by_id(self, db: Session, notification_id: UUID) -> Notification | None:
        return db.get(Notification, notification_id)

    def count_unread(self, db: Session, user_id: UUID) -> int:
        stmt = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
        return db.execute(stmt).scalar_one()

    def mark_all_read(self, db: Session, user_id: UUID) -> int:
        result = db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
            .values(is_read=True)
        )
        return result.rowcount

    def list_by_user(self, db: Session, user_id: UUID, limit: int = 50, offset: int = 0) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def create(self, db: Session, notification: Notification) -> Notification:
        db.add(notification)
        db.flush()
        return notification

    def update(self, db: Session, notification: Notification) -> Notification:
        db.add(notification)
        db.flush()
        return notification
