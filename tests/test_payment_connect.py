"""Tests for Stripe Connect Custom account onboarding flow."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.services.payment_service import PaymentService


# ── helpers ────────────────────────────────────────────────────────────────

def _make_service():
    return PaymentService(
        PaymentRepository(),
        BookingRepository(),
        TripRepository(),
        UserRepository(),
    )


def _make_driver(db_session, payment_details=None):
    driver = User(
        email=f"driver_{uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Password1!"),
        is_active=True,
        payment_details=payment_details,
    )
    db_session.add(driver)
    db_session.flush()
    return driver


def _valid_payload():
    return {
        "first_name": "James",
        "last_name": "Harrison",
        "dob": {"day": 15, "month": 6, "year": 1990},
        "address": {"line1": "12 Baker Street", "city": "London", "postal_code": "NW1 6XE"},
        "phone": "+447911123456",
        "account_holder_name": "James Harrison",
        "sort_code": "608371",
        "account_number": "12345678",
        "tos_accepted": True,
    }


def _mock_stripe_account(account_id="acct_test123", charges=False, payouts=False):
    acct = MagicMock()
    acct.id = account_id
    acct.get = lambda k, d=None: {
        "charges_enabled": charges,
        "payouts_enabled": payouts,
    }.get(k, d)
    return acct


# ── schema validation ───────────────────────────────────────────────────────

class TestConnectSchema:
    def test_sort_code_must_be_6_digits(self):
        from app.schemas.payment import ConnectOnboardRequest
        import pytest as _pytest
        from pydantic import ValidationError
        with _pytest.raises(ValidationError):
            ConnectOnboardRequest(**{**_valid_payload(), "sort_code": "6083"})

    def test_account_number_must_be_8_digits(self):
        from app.schemas.payment import ConnectOnboardRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ConnectOnboardRequest(**{**_valid_payload(), "account_number": "1234"})

    def test_sort_code_must_be_numeric(self):
        from app.schemas.payment import ConnectOnboardRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ConnectOnboardRequest(**{**_valid_payload(), "sort_code": "60-83-71"})

    def test_valid_payload_passes(self):
        from app.schemas.payment import ConnectOnboardRequest
        obj = ConnectOnboardRequest(**_valid_payload())
        assert obj.sort_code == "608371"
        assert obj.account_number == "12345678"


# ── service unit tests (Stripe mocked) ─────────────────────────────────────

class TestConnectOnboard:
    def test_raises_if_tos_not_accepted(self, db_session):
        service = _make_service()
        driver = _make_driver(db_session)
        payload = {**_valid_payload(), "tos_accepted": False}
        with patch("app.services.payment_service.get_settings") as mock_cfg:
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            with pytest.raises(ValueError, match="Terms of Service"):
                service.create_connect_account(db_session, driver.id, payload, "127.0.0.1")

    def test_raises_if_user_not_found(self, db_session):
        service = _make_service()
        with patch("app.services.payment_service.get_settings") as mock_cfg:
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            with pytest.raises(ValueError, match="User not found"):
                service.create_connect_account(db_session, uuid4(), _valid_payload(), "127.0.0.1")

    def test_creates_custom_account_and_saves_account_id(self, db_session):
        service = _make_service()
        driver = _make_driver(db_session)

        mock_account = _mock_stripe_account("acct_new123")
        mock_ext_account = MagicMock()

        with patch("app.services.payment_service.get_settings") as mock_cfg, \
             patch("stripe.Account.create", return_value=mock_account) as mock_create, \
             patch("stripe.Account.create_external_account", return_value=mock_ext_account), \
             patch("stripe.Account.retrieve", return_value=mock_account):
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"

            result = service.create_connect_account(db_session, driver.id, _valid_payload(), "127.0.0.1")

        assert result["account_id"] == "acct_new123"
        # Verify account type was "custom"
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["type"] == "custom"
        assert call_kwargs["country"] == "GB"
        # Verify driver record was updated
        db_session.refresh(driver)
        assert driver.payment_details == "acct_new123"

    def test_tos_acceptance_contains_ip_and_timestamp(self, db_session):
        service = _make_service()
        driver = _make_driver(db_session)

        mock_account = _mock_stripe_account("acct_tos123")

        with patch("app.services.payment_service.get_settings") as mock_cfg, \
             patch("stripe.Account.create", return_value=mock_account) as mock_create, \
             patch("stripe.Account.create_external_account"), \
             patch("stripe.Account.retrieve", return_value=mock_account):
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            service.create_connect_account(db_session, driver.id, _valid_payload(), "1.2.3.4")

        tos = mock_create.call_args[1]["tos_acceptance"]
        assert tos["ip"] == "1.2.3.4"
        assert isinstance(tos["date"], int) and tos["date"] > 0

    def test_individual_details_submitted_to_stripe(self, db_session):
        service = _make_service()
        driver = _make_driver(db_session)
        mock_account = _mock_stripe_account("acct_ind123")

        with patch("app.services.payment_service.get_settings") as mock_cfg, \
             patch("stripe.Account.create", return_value=mock_account) as mock_create, \
             patch("stripe.Account.create_external_account"), \
             patch("stripe.Account.retrieve", return_value=mock_account):
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            service.create_connect_account(db_session, driver.id, _valid_payload(), "127.0.0.1")

        individual = mock_create.call_args[1]["individual"]
        assert individual["first_name"] == "James"
        assert individual["last_name"] == "Harrison"
        assert individual["dob"] == {"day": 15, "month": 6, "year": 1990}
        assert individual["address"]["city"] == "London"
        assert individual["address"]["postal_code"] == "NW1 6XE"

    def test_bank_account_submitted_with_correct_fields(self, db_session):
        service = _make_service()
        driver = _make_driver(db_session)
        mock_account = _mock_stripe_account("acct_bank123")

        with patch("app.services.payment_service.get_settings") as mock_cfg, \
             patch("stripe.Account.create", return_value=mock_account), \
             patch("stripe.Account.create_external_account") as mock_bank, \
             patch("stripe.Account.retrieve", return_value=mock_account):
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            service.create_connect_account(db_session, driver.id, _valid_payload(), "127.0.0.1")

        bank_payload = mock_bank.call_args[1]["external_account"]
        assert bank_payload["object"] == "bank_account"
        assert bank_payload["currency"] == "gbp"
        assert bank_payload["routing_number"] == "608371"
        assert bank_payload["account_number"] == "12345678"
        assert bank_payload["account_holder_name"] == "James Harrison"

    def test_skips_account_creation_if_already_exists(self, db_session):
        service = _make_service()
        driver = _make_driver(db_session, payment_details="acct_existing")
        mock_account = _mock_stripe_account("acct_existing")

        with patch("app.services.payment_service.get_settings") as mock_cfg, \
             patch("stripe.Account.create") as mock_create, \
             patch("stripe.Account.create_external_account"), \
             patch("stripe.Account.retrieve", return_value=mock_account):
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            result = service.create_connect_account(db_session, driver.id, _valid_payload(), "127.0.0.1")

        # Should not create a new account
        mock_create.assert_not_called()
        assert result["account_id"] == "acct_existing"

    def test_stripe_error_raises_value_error(self, db_session):
        import stripe as _stripe
        service = _make_service()
        driver = _make_driver(db_session)

        with patch("app.services.payment_service.get_settings") as mock_cfg, \
             patch("stripe.Account.create", side_effect=_stripe.StripeError("card error")):
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            with pytest.raises(ValueError, match="Stripe error"):
                service.create_connect_account(db_session, driver.id, _valid_payload(), "127.0.0.1")


# ── document upload ─────────────────────────────────────────────────────────

class TestDocumentUpload:
    def test_upload_returns_file_id(self):
        service = _make_service()
        mock_file = MagicMock()
        mock_file.id = "file_abc123"

        with patch("app.services.payment_service.get_settings") as mock_cfg, \
             patch("stripe.File.create", return_value=mock_file):
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            result = service.upload_identity_document(uuid4(), b"fake_bytes", "front.jpg", "identity_document_front")

        assert result["file_id"] == "file_abc123"

    def test_attach_document_calls_stripe_modify(self, db_session):
        service = _make_service()
        driver = _make_driver(db_session, payment_details="acct_doc123")

        with patch("app.services.payment_service.get_settings") as mock_cfg, \
             patch("stripe.Account.modify") as mock_modify:
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            service.attach_identity_document(db_session, driver.id, "file_front", "file_back")

        mock_modify.assert_called_once()
        doc = mock_modify.call_args[1]["individual"]["verification"]["document"]
        assert doc["front"] == "file_front"
        assert doc["back"] == "file_back"

    def test_attach_document_without_back(self, db_session):
        service = _make_service()
        driver = _make_driver(db_session, payment_details="acct_doc456")

        with patch("app.services.payment_service.get_settings") as mock_cfg, \
             patch("stripe.Account.modify") as mock_modify:
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            service.attach_identity_document(db_session, driver.id, "file_front", None)

        doc = mock_modify.call_args[1]["individual"]["verification"]["document"]
        assert "front" in doc
        assert "back" not in doc

    def test_attach_raises_if_no_account(self, db_session):
        service = _make_service()
        driver = _make_driver(db_session)  # no payment_details

        with patch("app.services.payment_service.get_settings") as mock_cfg:
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            with pytest.raises(ValueError, match="no connected account|User not found"):
                service.attach_identity_document(db_session, driver.id, "file_front", None)


# ── status check ────────────────────────────────────────────────────────────

class TestConnectStatus:
    def test_returns_not_connected_when_no_account(self, db_session):
        service = _make_service()
        driver = _make_driver(db_session)

        with patch("app.services.payment_service.get_settings") as mock_cfg:
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            result = service.get_connect_status(db_session, driver.id)

        assert result["connected"] is False
        assert result["account_id"] is None

    def test_returns_connected_when_charges_enabled(self, db_session):
        service = _make_service()
        driver = _make_driver(db_session, payment_details="acct_live123")
        mock_account = _mock_stripe_account("acct_live123", charges=True, payouts=True)

        with patch("app.services.payment_service.get_settings") as mock_cfg, \
             patch("stripe.Account.retrieve", return_value=mock_account):
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            result = service.get_connect_status(db_session, driver.id)

        assert result["connected"] is True
        assert result["charges_enabled"] is True
        assert result["payouts_enabled"] is True
        assert result["account_id"] == "acct_live123"
