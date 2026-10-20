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

RAW_NONCE = "test-raw-nonce-abc123"

def _apple_claims(
    sub: str = "apple.uid.001",
    email: str = "user@privaterelay.appleid.com",
) -> dict:
    import hashlib
    return {
        "sub": sub,
        "email": email,
        "email_verified": "true",
        "is_private_email": "true",
        "iss": "https://appleid.apple.com",
        "aud": "com.rideway.app",
        "nonce": hashlib.sha256(RAW_NONCE.encode()).hexdigest(),
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
                raw_nonce=RAW_NONCE,
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
                raw_nonce=RAW_NONCE,
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
                db_session, "t", "c", raw_nonce=RAW_NONCE, first_name="First", last_name="Last"
            )
        db_session.commit()

        with patch.object(service, "_verify_apple_identity_token", return_value=claims):
            user2, _, _, is_new2 = service.apple_auth(
                db_session, "t", "c", raw_nonce=RAW_NONCE, first_name=None, last_name=None
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
                db_session, "t", "c", raw_nonce=RAW_NONCE, first_name=None, last_name=None
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
                service.apple_auth(db_session, "t", "c", raw_nonce=RAW_NONCE)


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
        import hashlib
        claims = {
            "email": "x@example.com",
            "nonce": hashlib.sha256(RAW_NONCE.encode()).hexdigest(),
        }  # no sub
        with patch.object(service, "_verify_apple_identity_token", return_value=claims):
            with pytest.raises(ValueError, match="missing user ID"):
                service.apple_auth(db_session, "t", "c", raw_nonce=RAW_NONCE)

    def test_nonce_mismatch_raises(self, service, db_session):
        """Wrong raw_nonce is rejected even with a valid token."""
        claims = _apple_claims(sub="apple.nonce.001")
        with patch.object(service, "_verify_apple_identity_token", return_value=claims):
            with pytest.raises(ValueError, match="Nonce"):
                service.apple_auth(db_session, "t", "c", raw_nonce="wrong-nonce")


# ── Refresh token storage + revocation on account deletion ───────────────────

class TestAppleRefreshTokenStorage:
    def test_sign_in_stores_refresh_token_from_authorization_code(self, service, db_session):
        """The exchange result is persisted so DELETE /me can revoke it later."""
        claims = _apple_claims(sub="apple.rt.001")
        with patch.object(service, "_verify_apple_identity_token", return_value=claims), \
             patch("app.services.auth_service.apple_service.exchange_authorization_code",
                   return_value="apple-refresh-token-xyz") as exchange:
            user, _, _, _ = service.apple_auth(
                db_session, "t", "auth-code-1", raw_nonce=RAW_NONCE, first_name="A", last_name="B"
            )
        db_session.commit()

        exchange.assert_called_once_with("auth-code-1")
        assert user.apple_refresh_token == "apple-refresh-token-xyz"

    def test_sign_in_survives_failed_exchange(self, service, db_session):
        """A failed exchange must not break sign-in — the account is still created."""
        claims = _apple_claims(sub="apple.rt.002")
        with patch.object(service, "_verify_apple_identity_token", return_value=claims), \
             patch("app.services.auth_service.apple_service.exchange_authorization_code",
                   return_value=None):
            user, access_token, _, is_new = service.apple_auth(
                db_session, "t", "auth-code-2", raw_nonce=RAW_NONCE
            )
        db_session.commit()

        assert is_new is True
        assert access_token
        assert user.apple_refresh_token is None


class TestDeleteAccountRevokesAppleToken:
    def _make_apple_user(self, db_session, refresh_token="apple-refresh-token-abc"):
        from app.models.user import User
        user = User(
            first_name="Apple",
            last_name="User",
            email="apple.delete@privaterelay.appleid.com",
            password_hash="unused",
            is_email_verified=True,
            apple_user_id="apple.delete.001",
            apple_refresh_token=refresh_token,
        )
        db_session.add(user)
        db_session.commit()
        return user

    def test_revokes_token_and_clears_it(self, db_session):
        from app.repositories.booking_repo import BookingRepository
        from app.repositories.user_repo import UserRepository
        from app.services.user_service import UserService

        user = self._make_apple_user(db_session)
        service = UserService(UserRepository(), BookingRepository())

        with patch("app.services.apple_service.revoke_token", return_value=True) as revoke:
            service.delete_account(db_session, user)
        db_session.commit()

        revoke.assert_called_once_with("apple-refresh-token-abc")
        assert user.apple_refresh_token is None
        assert user.is_active is False
        assert user.scheduled_deletion_at is not None

    def test_deletion_succeeds_when_revocation_fails(self, db_session):
        """An unreachable Apple (revoke returns False) must not block deletion."""
        from app.repositories.booking_repo import BookingRepository
        from app.repositories.user_repo import UserRepository
        from app.services.user_service import UserService

        user = self._make_apple_user(db_session)
        service = UserService(UserRepository(), BookingRepository())

        with patch("app.services.apple_service.revoke_token", return_value=False):
            service.delete_account(db_session, user)
        db_session.commit()

        assert user.is_active is False
        assert user.scheduled_deletion_at is not None

    def test_non_apple_user_does_not_call_apple(self, db_session):
        from app.models.user import User
        from app.repositories.booking_repo import BookingRepository
        from app.repositories.user_repo import UserRepository
        from app.services.user_service import UserService

        user = User(
            first_name="Email",
            last_name="User",
            email="email.delete@example.com",
            password_hash="unused",
            is_email_verified=True,
        )
        db_session.add(user)
        db_session.commit()

        service = UserService(UserRepository(), BookingRepository())
        with patch("app.services.apple_service.revoke_token") as revoke:
            service.delete_account(db_session, user)

        revoke.assert_not_called()


class TestAppleService:
    def _settings(self, **overrides):
        from types import SimpleNamespace
        base = {
            "apple_team_id": "TEAM123456",
            "apple_key_id": "KEY1234567",
            "apple_private_key": self._pem_key(),
            "apple_bundle_id": "com.rideway.app",
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    @staticmethod
    def _pem_key() -> str:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        key = ec.generate_private_key(ec.SECP256R1())
        return key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

    def test_is_configured_requires_key_material(self):
        from app.services import apple_service
        with patch("app.services.apple_service.get_settings", return_value=self._settings()):
            assert apple_service.is_configured() is True
        with patch("app.services.apple_service.get_settings",
                   return_value=self._settings(apple_team_id="")):
            assert apple_service.is_configured() is False

    def test_client_secret_is_valid_es256_jwt(self):
        from jose import jwt as jose_jwt
        from app.services import apple_service

        with patch("app.services.apple_service.get_settings", return_value=self._settings()):
            secret = apple_service._client_secret()

        claims = jose_jwt.get_unverified_claims(secret)
        assert claims["iss"] == "TEAM123456"
        assert claims["aud"] == "https://appleid.apple.com"
        assert claims["sub"] == "com.rideway.app"
        assert claims["exp"] > claims["iat"]

        header = jose_jwt.get_unverified_header(secret)
        assert header["alg"] == "ES256"
        assert header["kid"] == "KEY1234567"

    def test_revoke_posts_refresh_token_hint(self):
        from app.services import apple_service
        with patch("app.services.apple_service.get_settings", return_value=self._settings()), \
             patch("app.services.apple_service._client_secret", return_value="secret"), \
             patch("app.services.apple_service._post", return_value={}) as post:
            assert apple_service.revoke_token("refresh-tok") is True

        url, payload = post.call_args[0]
        assert url == "https://appleid.apple.com/auth/revoke"
        assert payload["token"] == "refresh-tok"
        assert payload["token_type_hint"] == "refresh_token"
        assert payload["client_id"] == "com.rideway.app"

    def test_revoke_noop_without_credentials(self):
        from app.services import apple_service
        with patch("app.services.apple_service.get_settings",
                   return_value=self._settings(apple_private_key="")), \
             patch("app.services.apple_service._post") as post:
            assert apple_service.revoke_token("refresh-tok") is False

        post.assert_not_called()

    def test_exchange_returns_refresh_token(self):
        from app.services import apple_service
        with patch("app.services.apple_service.get_settings", return_value=self._settings()), \
             patch("app.services.apple_service._client_secret", return_value="secret"), \
             patch("app.services.apple_service._post",
                   return_value={"refresh_token": "rt-123", "access_token": "at-123"}) as post:
            assert apple_service.exchange_authorization_code("code-abc") == "rt-123"

        url, payload = post.call_args[0]
        assert url == "https://appleid.apple.com/auth/token"
        assert payload["grant_type"] == "authorization_code"
        assert payload["code"] == "code-abc"
