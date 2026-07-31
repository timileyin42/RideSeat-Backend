"""User repository."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def get_by_id(self, db: Session, user_id: UUID) -> User | None:
        return db.get(User, user_id)

    def get_by_email(self, db: Session, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return db.execute(stmt).scalar_one_or_none()

    def create(self, db: Session, user: User) -> User:
        db.add(user)
        db.flush()
        return user

    def list_users(
        self,
        db: Session,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        role: str | None = None,
        verification_status: str | None = None,
    ) -> list[User]:
        stmt = select(User)
        if search:
            term = f"%{search}%"
            stmt = stmt.where(
                or_(
                    User.first_name.ilike(term),
                    User.last_name.ilike(term),
                    User.email.ilike(term),
                )
            )
        if role:
            stmt = stmt.where(User.role == role)
        if verification_status:
            stmt = stmt.where(User.identity_verification_status == verification_status)
        stmt = stmt.offset(offset).limit(limit)
        return list(db.execute(stmt).scalars().all())

    def count_users(self, db: Session, since=None) -> int:
        stmt = select(func.count(User.id))
        if since is not None:
            stmt = stmt.where(User.created_at >= since)
        return int(db.execute(stmt).scalar_one())

    def list_pending_verifications(self, db: Session, limit: int = 50, offset: int = 0) -> list[User]:
        from app.core.constants import IdentityVerificationStatus
        stmt = (
            select(User)
            .where(User.identity_verification_status == IdentityVerificationStatus.PENDING)
            .order_by(User.updated_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def update(self, db: Session, user: User) -> User:
        db.add(user)
        db.flush()
        return user

    def delete(self, db: Session, user: User) -> None:
        db.delete(user)
        db.flush()
