"""Tests for Sign in with Apple endpoint and service."""

import hashlib
import fakeredis
import pytest
from unittest.mock import patch

from app.repositories.user_repo import UserRepository
from app.services.auth_service import AuthService


# ── Stub email service ────────────────────────────────────────────────────────

class StubEmailService:
    def send_verification_email(self, *a, **kw): pass
    def send_welcome_email(self, *a, **kw): pass
    def send_password_reset_email(self, *a, **kw): pass


# ── Bypass passlib/bcrypt Python-3.14 incompatibility in local test env ──────
# Production runs in Docker with a compatible bcrypt version; this is test-only.

def _sha256_hash(password: str) -> str:
    return "sha256$" + hashlib.sha256(password.encode()).hexdigest()

def _sha256_verify(password: str, hashed: str) -> bool:
    return hashed == _sha256_hash(password)

@pytest.fixture(autouse=True)
def mock_bcrypt():
    # Patch where the names are looked up (the importing module), not where defined.
    with patch("app.services.auth_service.hash_password", side_effect=_sha256_hash), \
         patch("app.services.auth_service.verify_password", side_effect=_sha256_verify):
        yield


# ── Fake Apple token claims (what _verify_apple_identity_token returns) ───────

def _apple_claims(
    sub: str = "apple.uid.001",
    email: str = "user@privaterelay.appleid.com",
) -> dict:
    return {
        "sub": sub,
        "email": email,
        "email_verified": "true",
        "is_private_email": "true",
        "iss": "https://appleid.apple.com",
        "aud": "com.rideway.app",
    }


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fake_redis():
    store = fakeredis.FakeRedis(decode_responses=True)
    with patch("app.services.otp_service._client", return_value=store):
        yield store


@pytest.fixture()
def service(db_session):
    return AuthService(UserRepository(), StubEmailService())


# ── Helper: create + verify a normal user ────────────────────────────────────

def _make_verified_user(service, db, email="existing@example.com", password="pass1234"):
    import fakeredis
    from app.services import otp_service
    user, _, _ = service.register(db, email=email, password=password,
                                  first_name="Jane", last_name="Doe")
    db.commit()
    otp = otp_service.get_verify_otp(email)
    user, at, rt = service.verify_email(db, email, otp)
    db.commit()
    return user


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAppleAuthNewUser:
    def test_creates_account_on_first_sign_in(self, service, db_session):
        """New Apple user gets an account and receives tokens."""
        claims = _apple_claims(sub="apple.new.001", email="new@privaterelay.appleid.com")

        with patch.object(service, "_verify_apple_identity_token", return_value=claims):
            user, access_token, refresh_token, is_new = service.apple_auth(
                db_session,
                identity_token="fake.token",
                authorization_code="fake.code",
                first_name="Israel",
                last_name="Glory",
            )
        db_session.commit()

        assert is_new is True
        assert access_token
        assert refresh_token
        assert user.apple_user_id == "apple.new.001"
        assert user.first_name == "Israel"
        assert user.last_name == "Glory"
        assert user.is_email_verified is True

    def test_uses_apple_fallback_name_when_none_sent(self, service, db_session):
        """If Apple doesn't send name (subsequent logins), falls back to 'Apple User'."""
        claims = _apple_claims(sub="apple.noname.001")

        with patch.object(service, "_verify_apple_identity_token", return_value=claims):
            user, _, _, is_new = service.apple_auth(
                db_session,
                identity_token="fake.token",
                authorization_code="fake.code",
                first_name=None,
                last_name=None,
            )
        db_session.commit()

        assert is_new is True
        assert user.first_name == "Apple"
        assert user.last_name == "User"

    def test_second_sign_in_returns_existing_user(self, service, db_session):
        """Same apple_user_id on second sign-in returns same user, not a new one."""
        claims = _apple_claims(sub="apple.returning.001")

        with patch.object(service, "_verify_apple_identity_token", return_value=claims):
            user1, _, _, is_new1 = service.apple_auth(
                db_session, "t", "c", first_name="First", last_name="Last"
            )
        db_session.commit()

        with patch.object(service, "_verify_apple_identity_token", return_value=claims):
            user2, _, _, is_new2 = service.apple_auth(
                db_session, "t", "c", first_name=None, last_name=None
            )
        db_session.commit()

        assert is_new1 is True
        assert is_new2 is False
        assert user1.id == user2.id


class TestAppleAuthExistingEmailUser:
    def test_links_apple_id_to_existing_email_account(self, service, db_session):
        """User with email account can sign in with Apple — apple_user_id gets stamped on."""
        existing = _make_verified_user(service, db_session, email="linked@example.com")
        assert existing.apple_user_id is None

        claims = _apple_claims(sub="apple.link.001", email="linked@example.com")
        with patch.object(service, "_verify_apple_identity_token", return_value=claims):
            user, _, _, is_new = service.apple_auth(
                db_session, "t", "c", first_name=None, last_name=None
            )
        db_session.commit()

        assert is_new is False
        assert user.id == existing.id
        assert user.apple_user_id == "apple.link.001"

    def test_deactivated_user_is_blocked(self, service, db_session):
        """Deactivated account cannot sign in with Apple."""
        existing = _make_verified_user(service, db_session, email="gone@example.com")
        existing.is_active = False
        db_session.commit()

        claims = _apple_claims(sub="apple.gone.001", email="gone@example.com")
        with patch.object(service, "_verify_apple_identity_token", return_value=claims):
            with pytest.raises(ValueError, match="deactivated"):
                service.apple_auth(db_session, "t", "c")


class TestAppleAuthTokenVerification:
    def test_invalid_token_raises(self, service, db_session):
        """Garbage token string raises ValueError before touching the DB."""
        with pytest.raises(ValueError):
            service.apple_auth(
                db_session,
                identity_token="not.a.real.token",
                authorization_code="code",
            )

    def test_token_missing_sub_raises(self, service, db_session):
        """Claims without 'sub' are rejected."""
        claims = {"email": "x@example.com"}  # no sub
        with patch.object(service, "_verify_apple_identity_token", return_value=claims):
            with pytest.raises(ValueError, match="missing user ID"):
                service.apple_auth(db_session, "t", "c")
