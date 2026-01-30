"""Review repository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.review import Review


class ReviewRepository:
    def list_by_user(self, db: Session, user_id: UUID) -> list[Review]:
        stmt = select(Review).where(Review.reviewee_id == user_id)
        return list(db.execute(stmt).scalars().all())

    def create(self, db: Session, review: Review) -> Review:
        db.add(review)
        db.flush()
        return review
