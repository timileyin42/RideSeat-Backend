"""Authentication service."""

from datetime import timedelta
import secrets
from urllib import parse
from uuid import uuid4

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.email_service import EmailService
from app.utils.datetime import ensure_utc, now_utc


class AuthService:
    def __init__(self, user_repo: UserRepository, email_service: EmailService) -> None:
        self.user_repo = user_repo
        self.email_service = email_service

    def register(
        self,
        db: Session,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        phone_number: str | None,
    ) -> User:
        existing = self.user_repo.get_by_email(db, email)
        if existing:
            raise ValueError("Email already registered")
        otp_code = f"{secrets.randbelow(1000000):06d}"
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=hash_password(password),
            phone_number=phone_number,
            email_verification_token=otp_code,
            is_email_verified=False,
            email_verification_expires_at=now_utc() + timedelta(minutes=10),
        )
        saved = self.user_repo.create(db, user)
        self.email_service.send_verification_email(saved.email, saved.first_name, saved.email_verification_token)
        return saved

    def login(self, db: Session, email: str, password: str) -> tuple[User, str, str]:
        user = self.user_repo.get_by_email(db, email)
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")
        if not user.is_email_verified:
            raise ValueError("Email not verified")
        access_token, refresh_token = self._issue_tokens(user)
        return user, access_token, refresh_token

    def verify_email(self, db: Session, token: str) -> tuple[User, str, str]:
        user = self.user_repo.get_by_verification_token(db, token)
        if not user:
            raise ValueError("Invalid verification token")
        if not user.email_verification_expires_at or ensure_utc(user.email_verification_expires_at) < now_utc():
            raise ValueError("Verification token expired")
        user.is_email_verified = True
        user.email_verification_token = None
        user.email_verification_expires_at = None
        updated = self.user_repo.update(db, user)
        self.email_service.send_welcome_email(updated.email, updated.first_name)
        access_token, refresh_token = self._issue_tokens(updated)
        return updated, access_token, refresh_token

    def forgot_password(self, db: Session, email: str) -> User:
        user = self.user_repo.get_by_email(db, email)
        if not user:
            raise ValueError("User not found")
        user.password_reset_token = str(uuid4())
        user.password_reset_expires_at = now_utc() + timedelta(hours=2)
        saved = self.user_repo.update(db, user)
        self.email_service.send_password_reset_email(saved.email, saved.password_reset_token)
        return saved

    def reset_password(self, db: Session, token: str, new_password: str) -> User:
        user = self.user_repo.get_by_reset_token(db, token)
        if not user:
            raise ValueError("Invalid reset token")
        if not user.password_reset_expires_at or ensure_utc(user.password_reset_expires_at) < now_utc():
            raise ValueError("Reset token expired")
        user.password_hash = hash_password(new_password)
        user.password_reset_token = None
        user.password_reset_expires_at = None
        return self.user_repo.update(db, user)

    def google_auth(self, db: Session, id_token: str) -> tuple[User, str, str]:
        if not id_token:
            raise ValueError("Invalid Google token")
        token_info = self._verify_google_id_token(id_token)
        email = token_info.get("email")
        if not email:
            raise ValueError("Google token missing email")
        user = self.user_repo.get_by_email(db, email)
        if not user:
            first_name = token_info.get("given_name") or token_info.get("name") or "Google"
            last_name = token_info.get("family_name") or "User"
            user = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
                password_hash=hash_password(str(uuid4())),
                is_email_verified=True,
                email_verification_token=None,
                profile_photo_url=token_info.get("picture"),
            )
            user = self.user_repo.create(db, user)
        elif not user.is_email_verified:
            user.is_email_verified = True
            user.email_verification_token = None
            user.email_verification_expires_at = None
            user = self.user_repo.update(db, user)
        user = self._sync_google_profile(db, user, token_info)
        access_token, refresh_token = self._issue_tokens(user)
        return user, access_token, refresh_token

    def get_google_authorization_url(self, state: str | None = None) -> str:
        settings = get_settings()
        if not settings.google_client_id:
            raise ValueError("Google OAuth not configured")
        if not settings.mobile_app_scheme:
            raise ValueError("Mobile app scheme not configured")
        if not state:
            state = self._generate_state()
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.mobile_app_scheme,
            "scope": "openid email profile",
            "response_type": "code",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        query_string = parse.urlencode(params)
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"

    def _issue_tokens(self, user: User) -> tuple[str, str]:
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))
        return access_token, refresh_token

    def _verify_google_id_token(self, token: str) -> dict:
        settings = get_settings()
        allowed_audiences = [settings.google_client_id, settings.google_mobile_client_id]
        allowed_audiences = [aud for aud in allowed_audiences if aud]
        if not allowed_audiences:
            raise ValueError("Google OAuth not configured")
        try:
            token_info = google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
            )
        except ValueError as exc:
            raise ValueError("Invalid Google token") from exc
        audience = token_info.get("aud")
        if audience not in allowed_audiences:
            raise ValueError("Google token audience mismatch")
        return token_info

    def _generate_state(self) -> str:
        return secrets.token_urlsafe(32)

    def _sync_google_profile(self, db: Session, user: User, token_info: dict) -> User:
        updated = False
        given_name = token_info.get("given_name")
        family_name = token_info.get("family_name")
        picture = token_info.get("picture")

        if given_name and not user.first_name:
            user.first_name = given_name
            updated = True
        if family_name and not user.last_name:
            user.last_name = family_name
            updated = True
        if picture and not user.profile_photo_url:
            user.profile_photo_url = picture
            updated = True
        if not user.is_email_verified:
            user.is_email_verified = True
            user.email_verification_token = None
            user.email_verification_expires_at = None
            updated = True
        if updated:
            return self.user_repo.update(db, user)
        return user
