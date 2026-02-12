"""User service."""

from datetime import date, timedelta
import re
import secrets
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import UserRole
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.user_repo import UserRepository
from app.services.storage_service import StorageService
from app.utils.datetime import ensure_utc, now_utc
from app.utils.pagination import normalize_pagination


class UserService:
    def __init__(self, user_repo: UserRepository, booking_repo: BookingRepository) -> None:
        self.user_repo = user_repo
        self.booking_repo = booking_repo
        self.storage_service = StorageService()

    def get_user(self, db: Session, user_id: UUID) -> User:
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValueError("User not found")
        return user

    def update_user(self, db: Session, user: User, updates: dict) -> User:
        if "age_range" in updates and updates["age_range"] is not None:
            minimum_age = self._extract_min_age(updates["age_range"])
            if minimum_age < 18:
                raise ValueError("Age must be 18 or older")
        if "date_of_birth" in updates and updates["date_of_birth"] is not None:
            self._ensure_adult_by_dob(updates["date_of_birth"])
        if "phone_number" in updates and updates["phone_number"] is not None:
            user.is_phone_verified = False
            user.phone_verification_token = None
            user.phone_verification_expires_at = None
        if user.role == UserRole.PASSENGER and self._has_vehicle_updates(updates):
            user.role = UserRole.BOTH
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

    def update_vehicle_photo(self, db: Session, user: User, content: bytes, content_type: str | None) -> User:
        if not content_type or not content_type.startswith("image/"):
            raise ValueError("Vehicle photo must be an image")
        if len(content) > 5 * 1024 * 1024:
            raise ValueError("Vehicle photo file too large")
        photo_url = self.storage_service.upload_bytes(content, content_type, folder="vehicles")
        user.vehicle_photo_url = photo_url
        if user.role == UserRole.PASSENGER:
            user.role = UserRole.BOTH
        return self.user_repo.update(db, user)

    def list_users(self, db: Session, actor: User, limit: int | None = None, offset: int | None = None) -> list[User]:
        if not actor.is_admin:
            raise ValueError("Admin privileges required")
        pagination = normalize_pagination(limit, offset)
        return self.user_repo.list_users(db, limit=pagination.limit, offset=pagination.offset)

    def request_phone_verification(self, db: Session, user: User) -> str:
        if not user.phone_number:
            raise ValueError("Phone number required")
        token = f"{secrets.randbelow(1000000):06d}"
        user.phone_verification_token = token
        user.phone_verification_expires_at = now_utc() + timedelta(minutes=10)
        self.user_repo.update(db, user)
        return token

    def verify_phone(self, db: Session, user: User, code: str) -> User:
        if not user.phone_verification_token or user.phone_verification_token != code:
            raise ValueError("Invalid verification code")
        if not user.phone_verification_expires_at or ensure_utc(user.phone_verification_expires_at) < now_utc():
            raise ValueError("Verification code expired")
        user.is_phone_verified = True
        user.phone_verification_token = None
        user.phone_verification_expires_at = None
        return self.user_repo.update(db, user)

    def get_phone_for_driver(self, db: Session, actor: User, passenger_id: UUID) -> str:
        if actor.role not in {UserRole.DRIVER, UserRole.BOTH}:
            raise ValueError("Driver role required")
        allowed = self.booking_repo.has_confirmed_booking_between(db, actor.id, passenger_id)
        if not allowed:
            raise ValueError("Phone number not available")
        passenger = self.user_repo.get_by_id(db, passenger_id)
        if not passenger:
            raise ValueError("User not found")
        if not passenger.phone_number or not passenger.is_phone_verified:
            raise ValueError("Phone number not verified")
        return passenger.phone_number

    def get_playlist_url(self) -> str:
        settings = get_settings()
        return settings.spotify_playlist_url

    def list_promos(self) -> list[dict]:
        return [
            {
                "title": "RideSeat Promo",
                "description": "Limited time rider discount",
                "code": "RIDESEAT",
                "promo_type": "GENERAL",
            },
            {
                "title": "Student Promo",
                "description": "Discount for verified students",
                "code": "STUDENT",
                "promo_type": "STUDENT",
            },
        ]

    def get_student_promo(self) -> dict:
        for promo in self.list_promos():
            if promo["promo_type"] == "STUDENT":
                return promo
        raise ValueError("Student promo not available")

    def get_referral_url(self, user: User) -> str:
        settings = get_settings()
        if not settings.referral_base_url:
            raise ValueError("Referral link not configured")
        return f"{settings.referral_base_url}?ref={user.id}"

    def _extract_min_age(self, value: str) -> int:
        match = re.search(r"\d+", value)
        if not match:
            raise ValueError("Invalid age range")
        return int(match.group(0))

    def _ensure_adult_by_dob(self, value: date) -> None:
        today = now_utc().date()
        years = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if years < 18:
            raise ValueError("Age must be 18 or older")

    def _has_vehicle_updates(self, updates: dict) -> bool:
        vehicle_keys = {
            "vehicle_photo_url",
            "vehicle_make",
            "vehicle_model",
            "vehicle_type",
            "vehicle_color",
            "vehicle_year",
            "vehicle_plate",
            "luggage_size",
            "back_seat_max",
            "has_winter_tires",
            "allows_bikes",
            "allows_skis",
            "allows_snowboards",
            "allows_pets",
        }
        return any(updates.get(key) is not None for key in vehicle_keys)
