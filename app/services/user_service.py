"""User service."""

from datetime import date, timedelta
import logging
import re
import secrets

logger = logging.getLogger(__name__)
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import IdentityVerificationStatus
from app.models.user import User
from app.utils.uk_licence import validate_uk_licence
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
        updates = dict(updates)
        updates.pop("role", None)
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
        return self.user_repo.update(db, user)

    def list_users(
        self,
        db: Session,
        actor: User,
        limit: int | None = None,
        offset: int | None = None,
        search: str | None = None,
        role: str | None = None,
        verification_status: str | None = None,
    ) -> list[User]:
        if not actor.is_admin:
            raise ValueError("Admin privileges required")
        pagination = normalize_pagination(limit, offset)
        return self.user_repo.list_users(
            db,
            limit=pagination.limit,
            offset=pagination.offset,
            search=search,
            role=role,
            verification_status=verification_status,
        )

    def request_phone_verification(self, db: Session, phone_number: str, user=None) -> str:
        """Send OTP to phone_number. Saves to user profile if authenticated, else stores in Redis."""
        from app.services import otp_service
        token = f"{secrets.randbelow(1000000):06d}"
        if user is not None:
            user.phone_number = phone_number
            user.phone_verification_token = token
            user.phone_verification_expires_at = now_utc() + timedelta(minutes=10)
            self.user_repo.update(db, user)
        else:
            # Unauthenticated — store OTP in Redis keyed by phone number
            otp_service.set_phone_otp(phone_number, token)
        channel = otp_service.next_phone_channel(phone_number)
        logger.info("[DEV] Phone OTP for %s: %s", phone_number, token)
        self._send_phone_otp(phone_number, token, channel)
        return channel

    def _send_phone_otp(self, phone_number: str, token: str, channel: str) -> None:
        import json
        from urllib import request as http_request
        settings = get_settings()
        if not settings.termii_api_key or not settings.termii_sender_id:
            return  # Termii not configured — skip silently
        base_url = settings.termii_base_url.rstrip("/")

        payload = {
            "to": phone_number,
            "from": settings.termii_sender_id,
            "sms": f"Your Rideway verification code is {token}. Valid for 10 minutes.",
            "type": "plain",
            "channel": "generic",
            "api_key": settings.termii_api_key,
        }
        endpoint = f"{base_url}/api/sms/send"

        data = json.dumps(payload).encode("utf-8")
        req = http_request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with http_request.urlopen(req, timeout=10) as resp:
                resp_body = resp.read().decode("utf-8")
                logger.info("[TERMII] %s → %s %s", endpoint, resp.status, resp_body)
        except Exception as e:
            logger.warning("[TERMII] delivery failed: %s", e)

    def verify_phone(self, db: Session, code: str, phone_number: str | None = None, user=None) -> dict:
        from app.services import otp_service
        if user is not None:
            if not user.phone_verification_token or user.phone_verification_token != code:
                raise ValueError("Invalid verification code")
            if not user.phone_verification_expires_at or ensure_utc(user.phone_verification_expires_at) < now_utc():
                raise ValueError("Verification code expired")
            user.is_phone_verified = True
            user.phone_verification_token = None
            user.phone_verification_expires_at = None
            if user.phone_number:
                otp_service.reset_phone_channel(user.phone_number)
            return {"user": self.user_repo.update(db, user), "phone_number": user.phone_number}
        else:
            if not phone_number:
                raise ValueError("phone_number is required when not authenticated")
            stored = otp_service.get_phone_otp(phone_number)
            if not stored or stored != code:
                raise ValueError("Invalid verification code")
            otp_service.delete_phone_otp(phone_number)
            otp_service.reset_phone_channel(phone_number)
            return {"user": None, "phone_number": phone_number}

    def request_email_change(self, db: Session, user, new_email: str, email_service=None) -> None:
        from app.services import otp_service
        new_email = new_email.strip().lower()
        if new_email == (user.email or "").lower():
            raise ValueError("New email is the same as your current email")
        if self.user_repo.get_by_email(db, new_email):
            raise ValueError("That email address is already in use")
        token = f"{secrets.randbelow(1000000):06d}"
        otp_service.save_email_change_otp(str(user.id), new_email, token)
        logger.info("[DEV] Email change OTP for %s → %s: %s", user.email, new_email, token)
        if email_service:
            try:
                email_service.send_email_change_otp(new_email, user.first_name or "there", token)
            except Exception:
                pass

    def confirm_email_change(self, db: Session, user, code: str) -> None:
        from app.services import otp_service
        result = otp_service.get_email_change_otp(str(user.id))
        if not result:
            raise ValueError("No email change request found — please request a new code")
        new_email, stored_otp = result
        if stored_otp != code:
            raise ValueError("Invalid verification code")
        otp_service.delete_email_change_otp(str(user.id))
        user.email = new_email
        user.is_email_verified = True
        self.user_repo.update(db, user)

    def get_phone_for_driver(self, db: Session, actor: User, passenger_id: UUID) -> str:
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

    def submit_driver_license(
        self,
        db: Session,
        user: User,
        licence_number: str,
        content: bytes,
        content_type: str | None,
        email_service=None,
        vision_service=None,
        back_content: bytes | None = None,
        back_content_type: str | None = None,
    ) -> User:
        if not content_type or not content_type.startswith("image/"):
            raise ValueError("Driver licence front photo must be an image")
        if len(content) > 10 * 1024 * 1024:
            raise ValueError("File too large (max 10 MB)")
        if back_content and (not back_content_type or not back_content_type.startswith("image/")):
            raise ValueError("Driver licence back photo must be an image")
        if back_content and len(back_content) > 10 * 1024 * 1024:
            raise ValueError("Back photo too large (max 10 MB)")
        is_valid, reason = validate_uk_licence(
            licence_number,
            last_name=user.last_name or None,
            date_of_birth=user.date_of_birth or None,
        )
        if not is_valid:
            raise ValueError(f"Licence validation failed: {reason}")
        if vision_service is not None:
            try:
                extracted = vision_service.extract_licence_number(content)
                normalised = licence_number.replace(" ", "").upper()
                if extracted and extracted != normalised:
                    raise ValueError(
                        f"Photo does not match submitted licence number "
                        f"(detected {extracted}, submitted {normalised})"
                    )
            except ValueError:
                raise
            except Exception:
                pass  # OCR unavailable — fall back to admin manual review
        url = self.storage_service.upload_bytes(content, content_type, folder="driver_licences")
        user.driver_license_url = url
        if back_content and back_content_type:
            back_url = self.storage_service.upload_bytes(back_content, back_content_type, folder="driver_licences")
            user.driver_license_back_url = back_url
        user.driver_license_number = licence_number.replace(" ", "").upper()
        user.identity_verification_status = IdentityVerificationStatus.PENDING
        updated = self.user_repo.update(db, user)
        if email_service:
            settings = get_settings()
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            if settings.admin_email:
                email_service.send_admin_verification_alert(
                    admin_email=settings.admin_email,
                    driver_name=full_name or "Unknown",
                    driver_email=user.email,
                    driver_id=str(user.id),
                )
            email_service.send_verification_submitted_email(
                email=user.email,
                first_name=user.first_name or "there",
            )
        return updated

    def submit_selfie(self, db: Session, user: User, content: bytes, content_type: str | None) -> User:
        if not content_type or not content_type.startswith("image/"):
            raise ValueError("Selfie must be an image")
        if len(content) > 10 * 1024 * 1024:
            raise ValueError("Selfie file too large")
        url = self.storage_service.upload_bytes(content, content_type, folder="selfies")
        user.selfie_url = url
        if user.identity_verification_status is None:
            user.identity_verification_status = IdentityVerificationStatus.PENDING
        return self.user_repo.update(db, user)

    def submit_id_document(self, db: Session, user: User, content: bytes, content_type: str | None) -> User:
        if not content_type or not content_type.startswith("image/"):
            raise ValueError("ID document must be an image")
        if len(content) > 10 * 1024 * 1024:
            raise ValueError("ID document file too large")
        url = self.storage_service.upload_bytes(content, content_type, folder="id_documents")
        user.id_document_url = url
        if user.identity_verification_status is None:
            user.identity_verification_status = IdentityVerificationStatus.PENDING
        return self.user_repo.update(db, user)

    def approve_identity(self, db: Session, actor: User, user_id: UUID, email_service=None) -> User:
        if not actor.is_admin:
            raise ValueError("Admin privileges required")
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValueError("User not found")
        user.identity_verified = True
        user.identity_verification_status = IdentityVerificationStatus.APPROVED
        updated = self.user_repo.update(db, user)
        if email_service:
            email_service.send_verification_approved_email(
                email=user.email,
                first_name=user.first_name or "there",
            )
        return updated

    def reject_identity(self, db: Session, actor: User, user_id: UUID, reason: str | None = None, email_service=None) -> User:
        if not actor.is_admin:
            raise ValueError("Admin privileges required")
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValueError("User not found")
        user.identity_verified = False
        user.identity_verification_status = IdentityVerificationStatus.REJECTED
        updated = self.user_repo.update(db, user)
        if email_service:
            email_service.send_verification_rejected_email(
                email=user.email,
                first_name=user.first_name or "there",
                reason=reason,
            )
        return updated

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

    def delete_account(self, db: Session, user: User) -> None:
        self.user_repo.delete(db, user)
