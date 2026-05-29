import fakeredis
import pytest
from unittest.mock import patch

from app.repositories.user_repo import UserRepository
from app.services.auth_service import AuthService
from app.services import otp_service


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


@pytest.fixture(autouse=True)
def fake_redis():
    """Redirect all OTP Redis calls to an in-process fake store."""
    store = fakeredis.FakeRedis(decode_responses=True)
    with patch("app.services.otp_service._client", return_value=store):
        yield store


def test_register_verify_login(db_session, fake_redis):
    repo = UserRepository()
    email_service = StubEmailService()
    service = AuthService(repo, email_service)

    user = service.register(db_session, "Ada", "Lovelace", "ada@example.com", "pass1234", None)
    db_session.commit()

    assert email_service.verification_emails[0][0] == "ada@example.com"
    token = email_service.verification_emails[0][2]

    # OTP should be in Redis
    assert otp_service.get_verify_otp("ada@example.com") == token

    verified_user, access_token, refresh_token = service.verify_email(
        db_session, "ada@example.com", token
    )
    db_session.commit()

    assert email_service.welcome_emails[0][0] == "ada@example.com"
    assert access_token
    assert refresh_token
    assert verified_user.is_email_verified
    # OTP should be deleted from Redis after successful verification
    assert otp_service.get_verify_otp("ada@example.com") is None

    logged_in_user, access_token, refresh_token = service.login(
        db_session, "ada@example.com", "pass1234"
    )
    assert access_token
    assert refresh_token
    assert logged_in_user.id


def test_forgot_password_sends_email(db_session, fake_redis):
    repo = UserRepository()
    email_service = StubEmailService()
    service = AuthService(repo, email_service)

    user = service.register(db_session, "Grace", "Hopper", "grace@example.com", "pass1234", None)
    db_session.commit()

    service.forgot_password(db_session, user.email)

    assert email_service.reset_emails[0][0] == "grace@example.com"
    # Reset OTP should be in Redis
    otp = email_service.reset_emails[0][1]
    assert otp_service.get_reset_otp("grace@example.com") == otp


def test_verify_email_rejects_expired_token(db_session, fake_redis):
    """Simulate expiry by deleting the key from Redis before verification."""
    repo = UserRepository()
    email_service = StubEmailService()
    service = AuthService(repo, email_service)

    service.register(db_session, "Expired", "Token", "expired@example.com", "pass1234", None)
    db_session.commit()

    # Simulate TTL expiry by deleting the Redis key
    otp_service.delete_verify_otp("expired@example.com")

    with pytest.raises(ValueError, match="Invalid or expired"):
        service.verify_email(db_session, "expired@example.com", "000000")
