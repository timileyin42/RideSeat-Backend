"""User repository."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def get_by_id(self, db: Session, user_id: UUID) -> User | None:
        return db.get(User, user_id)

    def get_by_email(self, db: Session, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return db.execute(stmt).scalar_one_or_none()

    def get_by_verification_token(self, db: Session, token: str) -> User | None:
        stmt = select(User).where(User.email_verification_token == token)
        return db.execute(stmt).scalar_one_or_none()

    def get_by_reset_token(self, db: Session, token: str) -> User | None:
        stmt = select(User).where(User.password_reset_token == token)
        return db.execute(stmt).scalar_one_or_none()

    def create(self, db: Session, user: User) -> User:
        db.add(user)
        db.flush()
        return user

    def list_users(self, db: Session, limit: int = 50, offset: int = 0) -> list[User]:
        stmt = select(User).offset(offset).limit(limit)
        return list(db.execute(stmt).scalars().all())

    def count_users(self, db: Session) -> int:
        stmt = select(func.count(User.id))
        return int(db.execute(stmt).scalar_one())

    def update(self, db: Session, user: User) -> User:
        db.add(user)
        db.flush()
        return user
