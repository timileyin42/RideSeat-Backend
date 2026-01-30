"""User service."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.storage_service import StorageService
from app.utils.pagination import normalize_pagination


class UserService:
    def __init__(self, user_repo: UserRepository) -> None:
        self.user_repo = user_repo
        self.storage_service = StorageService()

    def get_user(self, db: Session, user_id: UUID) -> User:
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValueError("User not found")
        return user

    def update_user(self, db: Session, user: User, updates: dict) -> User:
        for key, value in updates.items():
            if value is not None:
                setattr(user, key, value)
        return self.user_repo.update(db, user)

    def update_avatar(self, db: Session, user: User, content: bytes, content_type: str | None) -> User:
        if not content_type or not content_type.startswith("image/"):
            raise ValueError("Avatar must be an image")
        if len(content) > 5 * 1024 * 1024:
            raise ValueError("Avatar file too large")
        photo_url = self.storage_service.upload_bytes(content, content_type, folder="avatars")
        user.profile_photo_url = photo_url
        return self.user_repo.update(db, user)

    def list_users(self, db: Session, actor: User, limit: int | None = None, offset: int | None = None) -> list[User]:
        if not actor.is_admin:
            raise ValueError("Admin privileges required")
        pagination = normalize_pagination(limit, offset)
        return self.user_repo.list_users(db, limit=pagination.limit, offset=pagination.offset)
