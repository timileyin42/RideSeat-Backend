from datetime import timedelta

import pytest

from app.repositories.user_repo import UserRepository
from app.services.auth_service import AuthService
from app.utils.datetime import now_utc


class StubEmailService:
    def __init__(self) -> None:
        self.verification_emails: list[tuple[str, str, str]] = []
        self.reset_emails: list[tuple[str, str]] = []
        self.welcome_emails: list[tuple[str, str]] = []

    def send_verification_email(self, email: str, first_name: str, token: str) -> None:
        self.verification_emails.append((email, first_name, token))

    def send_password_reset_email(self, email: str, token: str) -> None:
        self.reset_emails.append((email, token))

    def send_welcome_email(self, email: str, first_name: str) -> None:
        self.welcome_emails.append((email, first_name))

    def send_trip_completed_email(self, *args, **kwargs) -> None:
        return None


def test_register_verify_login(db_session):
    repo = UserRepository()
    email_service = StubEmailService()
    service = AuthService(repo, email_service)

    user = service.register(db_session, "Ada", "Lovelace", "ada@example.com", "pass1234", None)
    db_session.commit()

    assert email_service.verification_emails[0][0] == "ada@example.com"
    token = email_service.verification_emails[0][2]

    verified_user, access_token, refresh_token = service.verify_email(db_session, token)
    db_session.commit()

    assert email_service.welcome_emails[0][0] == "ada@example.com"
    assert access_token
    assert refresh_token
    assert verified_user.is_email_verified

    logged_in_user, access_token, refresh_token = service.login(db_session, "ada@example.com", "pass1234")
    assert access_token
    assert refresh_token
    assert logged_in_user.id


def test_forgot_password_sends_email(db_session):
    repo = UserRepository()
    email_service = StubEmailService()
    service = AuthService(repo, email_service)

    user = service.register(db_session, "Grace", "Hopper", "grace@example.com", "pass1234", None)
    db_session.commit()

    service.forgot_password(db_session, user.email)
    db_session.commit()

    assert email_service.reset_emails[0][0] == "grace@example.com"


def test_verify_email_rejects_expired_token(db_session):
    repo = UserRepository()
    email_service = StubEmailService()
    service = AuthService(repo, email_service)

    user = service.register(db_session, "Expired", "Token", "expired@example.com", "pass1234", None)
    user.email_verification_expires_at = now_utc() - timedelta(minutes=1)
    db_session.commit()

    token = email_service.verification_emails[0][2]

    with pytest.raises(ValueError):
        service.verify_email(db_session, token)
