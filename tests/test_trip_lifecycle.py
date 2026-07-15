"""Tests for trip start/complete lifecycle and manual payout request."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.constants import BookingStatus, TripStatus
from app.core.security import hash_password
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.trip import Trip
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.services.payment_service import PaymentService
from app.services.trip_service import TripService


# ── helpers ────────────────────────────────────────────────────────────────

def _make_trip_service():
    return TripService(TripRepository())


def _make_payment_service():
    return PaymentService(
        PaymentRepository(), BookingRepository(), TripRepository(), UserRepository()
    )


def _make_user(db, payment_details=None):
    u = User(
        email=f"user_{uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Password1!"),
        is_active=True,
        payment_details=payment_details,
    )
    db.add(u)
    db.flush()
    return u


def _make_trip(db, driver, status="ACTIVE"):
    t = Trip(
        driver_id=driver.id,
        origin_city="London",
        destination_city="Manchester",
        departure_time=datetime.now(timezone.utc) + timedelta(hours=2),
        available_seats=3,
        price_per_seat=20.0,
        toll_fee=0,
        vehicle_make="Toyota",
        vehicle_model="Prius",
        vehicle_color="Silver",
        trip_status=status,
    )
    db.add(t)
    db.flush()
    return t


def _make_booking(db, trip, passenger, status=BookingStatus.CONFIRMED):
    b = Booking(
        trip_id=trip.id,
        passenger_id=passenger.id,
        seats=1,
        total_amount=20.0,
        status=status,
    )
    db.add(b)
    db.flush()
    return b


def _make_payment(db, booking, transfer_id=None):
    p = Payment(
        booking_id=booking.id,
        amount=20.0,
        platform_fee=2.0,
        payout_amount=18.0,
        status="SUCCEEDED",
        stripe_payment_intent_id="pi_test",
        stripe_transfer_id=transfer_id,
    )
    db.add(p)
    db.flush()
    return p


# ── start_trip ─────────────────────────────────────────────────────────────

class TestStartTrip:
    def test_sets_status_to_started(self, db_session):
        svc = _make_trip_service()
        driver = _make_user(db_session)
        trip = _make_trip(db_session, driver)

        result = svc.start_trip(db_session, driver, trip.id)

        assert result["trip_status"] == TripStatus.STARTED
        assert result["started_at"] is not None

    def test_wrong_driver_raises(self, db_session):
        svc = _make_trip_service()
        driver = _make_user(db_session)
        other = _make_user(db_session)
        trip = _make_trip(db_session, driver)

        with pytest.raises(ValueError, match="Not allowed"):
            svc.start_trip(db_session, other, trip.id)

    def test_cannot_start_already_started(self, db_session):
        svc = _make_trip_service()
        driver = _make_user(db_session)
        trip = _make_trip(db_session, driver, status="STARTED")

        with pytest.raises(ValueError, match="cannot be started"):
            svc.start_trip(db_session, driver, trip.id)

    def test_cannot_start_completed_trip(self, db_session):
        svc = _make_trip_service()
        driver = _make_user(db_session)
        trip = _make_trip(db_session, driver, status="COMPLETED")

        with pytest.raises(ValueError, match="cannot be started"):
            svc.start_trip(db_session, driver, trip.id)

    def test_trip_not_found_raises(self, db_session):
        svc = _make_trip_service()
        driver = _make_user(db_session)

        with pytest.raises(ValueError, match="Trip not found"):
            svc.start_trip(db_session, driver, uuid4())


# ── complete_trip ───────────────────────────────────────────────────────────

class TestCompleteTrip:
    def test_sets_status_to_completed(self, db_session):
        svc = _make_trip_service()
        driver = _make_user(db_session)
        trip = _make_trip(db_session, driver, status="STARTED")

        result = svc.complete_trip(db_session, driver, trip.id)

        assert result["trip_status"] == TripStatus.COMPLETED
        assert result["completed_at"] is not None

    def test_marks_confirmed_bookings_completed(self, db_session):
        svc = _make_trip_service()
        driver = _make_user(db_session)
        passenger = _make_user(db_session)
        trip = _make_trip(db_session, driver, status="STARTED")
        booking = _make_booking(db_session, trip, passenger, BookingStatus.CONFIRMED)

        svc.complete_trip(db_session, driver, trip.id)

        db_session.refresh(booking)
        assert booking.status == BookingStatus.COMPLETED

    def test_does_not_affect_cancelled_bookings(self, db_session):
        svc = _make_trip_service()
        driver = _make_user(db_session)
        passenger = _make_user(db_session)
        trip = _make_trip(db_session, driver, status="STARTED")
        booking = _make_booking(db_session, trip, passenger, BookingStatus.CANCELLED)

        svc.complete_trip(db_session, driver, trip.id)

        db_session.refresh(booking)
        assert booking.status == BookingStatus.CANCELLED

    def test_cannot_complete_active_trip(self, db_session):
        svc = _make_trip_service()
        driver = _make_user(db_session)
        trip = _make_trip(db_session, driver, status="ACTIVE")

        with pytest.raises(ValueError, match="cannot be completed"):
            svc.complete_trip(db_session, driver, trip.id)

    def test_wrong_driver_raises(self, db_session):
        svc = _make_trip_service()
        driver = _make_user(db_session)
        other = _make_user(db_session)
        trip = _make_trip(db_session, driver, status="STARTED")

        with pytest.raises(ValueError, match="Not allowed"):
            svc.complete_trip(db_session, other, trip.id)


# ── request_payout ──────────────────────────────────────────────────────────

class TestRequestPayout:
    def test_returns_zero_when_no_pending_payments(self, db_session):
        svc = _make_payment_service()
        driver = _make_user(db_session, payment_details="acct_test")

        with patch("app.services.payment_service.get_settings") as mock_cfg:
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            result = svc.request_payout(db_session, driver.id)

        assert result["transfers_initiated"] == 0

    def test_raises_if_no_connected_account(self, db_session):
        svc = _make_payment_service()
        driver = _make_user(db_session)  # no payment_details

        with patch("app.services.payment_service.get_settings") as mock_cfg:
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            with pytest.raises(ValueError, match="payout account"):
                svc.request_payout(db_session, driver.id)

    def test_raises_if_user_not_found(self, db_session):
        svc = _make_payment_service()

        with patch("app.services.payment_service.get_settings") as mock_cfg:
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            with pytest.raises(ValueError, match="User not found"):
                svc.request_payout(db_session, uuid4())

    def test_initiates_transfer_for_unpaid_booking(self, db_session):
        svc = _make_payment_service()
        driver = _make_user(db_session, payment_details="acct_drv")
        passenger = _make_user(db_session)
        trip = _make_trip(db_session, driver, status="COMPLETED")
        booking = _make_booking(db_session, trip, passenger, BookingStatus.COMPLETED)
        _make_payment(db_session, booking)

        mock_transfer = MagicMock()
        mock_transfer.id = "tr_test123"

        with patch("app.services.payment_service.get_settings") as mock_cfg, \
             patch("stripe.Transfer.create", return_value=mock_transfer):
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            result = svc.request_payout(db_session, driver.id)

        assert result["transfers_initiated"] == 1
        assert result["total_amount"] == 18.0

    def test_skips_already_paid_bookings(self, db_session):
        svc = _make_payment_service()
        driver = _make_user(db_session, payment_details="acct_drv2")
        passenger = _make_user(db_session)
        trip = _make_trip(db_session, driver, status="COMPLETED")
        booking = _make_booking(db_session, trip, passenger, BookingStatus.COMPLETED)
        _make_payment(db_session, booking, transfer_id="tr_already_done")

        with patch("app.services.payment_service.get_settings") as mock_cfg:
            mock_cfg.return_value.stripe_secret_key = "sk_test_fake"
            result = svc.request_payout(db_session, driver.id)

        assert result["transfers_initiated"] == 0
