"""Tests confirming all design gaps are resolved.

Covers gaps: #1 addresses, #2 instant booking, #4 per-trip prefs, #5 identity verification,
#6 duration/arrival, #7 title, #8 stops, #9 search sort, #10 passport, #11 pending count,
#12 is_verified badge, #13 trips_completed in public response.
"""

from datetime import timedelta

import pytest

from app.core.constants import BookingMode, BookingStatus, IdentityVerificationStatus, UserRole
from app.core.security import hash_password
from app.models.booking import Booking
from app.models.trip import Trip
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.schemas.trip import TripCreate, TripResponse
from app.schemas.user import UserPublicResponse, UserPrivateResponse
from app.services.trip_service import TripService
from app.services.user_service import UserService
from app.utils.datetime import now_utc


class _StubEmailService:
    def send_booking_request_email(self, *_, **__): pass
    def send_trip_completed_email(self, *_, **__): pass
    def send_verification_email(self, *_, **__): pass
    def send_password_reset_email(self, *_, **__): pass


class _StubPaymentService:
    def trigger_payout_background(self, _): pass


class _StubNotificationService:
    def create_notification(self, *_, **__): pass


def _make_booking_service():
    from app.services.booking_service import BookingService
    return BookingService(
        BookingRepository(), TripRepository(), UserRepository(),
        _StubEmailService(), _StubNotificationService(), _StubPaymentService(),
    )


# ── helpers ──────────────────────────────────────────────────────────────────


def make_driver(db, email="driver@example.com"):
    repo = UserRepository()
    u = repo.create(db, User(
        first_name="Driver", last_name="Test",
        email=email, password_hash=hash_password("pass1234"),
        role=UserRole.DRIVER, is_email_verified=True,
    ))
    db.commit()
    return u


def make_passenger(db, email="passenger@example.com"):
    repo = UserRepository()
    u = repo.create(db, User(
        first_name="Passenger", last_name="Test",
        email=email, password_hash=hash_password("pass1234"),
        role=UserRole.PASSENGER, is_email_verified=True,
    ))
    db.commit()
    return u


def base_trip_data(**kwargs):
    data = {
        "origin_city": "Lagos",
        "destination_city": "Abuja",
        "departure_time": now_utc() + timedelta(hours=4),
        "available_seats": 3,
        "price_per_seat": 20,
        "vehicle_make": "Toyota",
        "vehicle_model": "Camry",
        "vehicle_color": "Black",
        "luggage_allowed": False,
    }
    data.update(kwargs)
    return data


# ── Gap #1: Full street addresses ─────────────────────────────────────────────


def test_trip_stores_full_addresses(db_session):
    driver = make_driver(db_session, "addr-driver@example.com")
    trip_repo = TripRepository()

    trip = trip_repo.create(db_session, Trip(
        driver_id=driver.id,
        origin_city="Lagos",
        destination_city="Abuja",
        origin_address="14 Ocean Ave, Lagos Island, Lagos 101001",
        destination_address="22 Wuse Zone 5, Abuja 900281",
        origin_lat=6.4541,
        origin_lng=3.3947,
        destination_lat=9.0579,
        destination_lng=7.4951,
        departure_time=now_utc() + timedelta(hours=2),
        available_seats=2,
        price_per_seat=30,
        vehicle_make="Honda",
        vehicle_model="Accord",
        vehicle_color="Blue",
    ))
    db_session.commit()

    assert trip.origin_address == "14 Ocean Ave, Lagos Island, Lagos 101001"
    assert trip.destination_address == "22 Wuse Zone 5, Abuja 900281"
    assert trip.origin_lat == pytest.approx(6.4541)
    assert trip.destination_lng == pytest.approx(7.4951)


# ── Gap #2: Instant booking ───────────────────────────────────────────────────


def test_instant_booking_flag_defaults_false(db_session):
    driver = make_driver(db_session, "ib-driver@example.com")
    trip_repo = TripRepository()
    service = TripService(trip_repo)

    result = service.create_trip(db_session, driver, base_trip_data())
    db_session.commit()

    assert result["instant_booking"] is False
    assert result["booking_mode"] == BookingMode.REVIEW_REQUESTS


def test_instant_booking_creates_confirmed_booking(db_session):
    driver = make_driver(db_session, "ib-confirm-driver@example.com")
    passenger = make_passenger(db_session, "ib-confirm-pax@example.com")
    trip_repo = TripRepository()

    trip = trip_repo.create(db_session, Trip(
        driver_id=driver.id,
        instant_booking=True,
        **base_trip_data(),
    ))
    db_session.commit()

    booking = _make_booking_service().create_booking(db_session, passenger, trip.id, 1)
    assert booking.status == BookingStatus.CONFIRMED


def test_non_instant_booking_creates_pending_booking(db_session):
    driver = make_driver(db_session, "pending-driver@example.com")
    passenger = make_passenger(db_session, "pending-pax@example.com")
    trip_repo = TripRepository()

    trip = trip_repo.create(db_session, Trip(
        driver_id=driver.id,
        instant_booking=False,
        **base_trip_data(),
    ))
    db_session.commit()

    booking = _make_booking_service().create_booking(db_session, passenger, trip.id, 1)
    assert booking.status == BookingStatus.PENDING


def test_driver_booking_list_returns_empty_for_non_driver(db_session):
    passenger = make_passenger(db_session, "driver-list-pax@example.com")

    bookings = _make_booking_service().list_bookings_for_driver(db_session, passenger)

    assert bookings == []


def test_driver_can_get_passenger_phone_without_role_switch(db_session):
    driver = make_passenger(db_session, "phone-driver@example.com")
    passenger = make_passenger(db_session, "phone-passenger@example.com")
    passenger.phone_number = "+447911123456"
    passenger.is_phone_verified = True
    UserRepository().update(db_session, passenger)

    trip = TripRepository().create(db_session, Trip(
        driver_id=driver.id,
        **base_trip_data(),
    ))
    BookingRepository().create(db_session, Booking(
        trip_id=trip.id,
        passenger_id=passenger.id,
        seats=1,
        status=BookingStatus.CONFIRMED,
        total_amount=20,
    ))
    db_session.commit()

    phone_number = UserService(UserRepository(), BookingRepository()).get_phone_for_driver(
        db_session,
        driver,
        passenger.id,
    )

    assert phone_number == "+447911123456"


# ── Gap #4: Per-trip preferences ─────────────────────────────────────────────


def test_trip_preferences_stored_correctly(db_session):
    driver = make_driver(db_session, "prefs-driver@example.com")
    trip_repo = TripRepository()
    service = TripService(trip_repo)

    result = service.create_trip(db_session, driver, base_trip_data(
        music_allowed=True,
        pets_allowed=False,
        smoking_allowed=False,
        air_conditioning=True,
        minimal_luggage=True,
    ))
    db_session.commit()

    assert result["music_allowed"] is True
    assert result["air_conditioning"] is True
    assert result["minimal_luggage"] is True
    assert result["pets_allowed"] is False
    assert result["smoking_allowed"] is False


# ── Gap #5: Identity verification ────────────────────────────────────────────


def test_identity_verification_status_defaults_none(db_session):
    repo = UserRepository()
    user = repo.create(db_session, User(
        first_name="New", last_name="User",
        email="new-user-iv@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.PASSENGER, is_email_verified=True,
    ))
    db_session.commit()

    assert user.identity_verified is False
    assert user.identity_verification_status is None


def test_admin_approve_identity(db_session):
    user_repo = UserRepository()
    service = UserService(user_repo, BookingRepository())

    admin = user_repo.create(db_session, User(
        first_name="Admin", last_name="User",
        email="admin-iv@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.PASSENGER, is_email_verified=True, is_admin=True,
    ))
    target = user_repo.create(db_session, User(
        first_name="Target", last_name="User",
        email="target-iv@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.PASSENGER, is_email_verified=True,
    ))
    db_session.commit()

    updated = service.approve_identity(db_session, admin, target.id)
    assert updated.identity_verified is True
    assert updated.identity_verification_status == IdentityVerificationStatus.APPROVED


def test_admin_reject_identity(db_session):
    user_repo = UserRepository()
    service = UserService(user_repo, BookingRepository())

    admin = user_repo.create(db_session, User(
        first_name="Admin2", last_name="User",
        email="admin2-iv@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.PASSENGER, is_email_verified=True, is_admin=True,
    ))
    target = user_repo.create(db_session, User(
        first_name="Target2", last_name="User",
        email="target2-iv@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.PASSENGER, is_email_verified=True,
    ))
    db_session.commit()

    updated = service.reject_identity(db_session, admin, target.id)
    assert updated.identity_verified is False
    assert updated.identity_verification_status == IdentityVerificationStatus.REJECTED


def test_non_admin_cannot_approve_identity(db_session):
    user_repo = UserRepository()
    service = UserService(user_repo, BookingRepository())

    non_admin = user_repo.create(db_session, User(
        first_name="Regular", last_name="User",
        email="regular-iv@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.PASSENGER, is_email_verified=True, is_admin=False,
    ))
    target = user_repo.create(db_session, User(
        first_name="Target3", last_name="User",
        email="target3-iv@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.PASSENGER, is_email_verified=True,
    ))
    db_session.commit()

    with pytest.raises(ValueError, match="Admin privileges required"):
        service.approve_identity(db_session, non_admin, target.id)


# ── Gap #6: Estimated duration & arrival time ─────────────────────────────────


def test_trip_duration_and_arrival_time(db_session):
    driver = make_driver(db_session, "dur-driver@example.com")
    trip_repo = TripRepository()
    service = TripService(trip_repo)

    dep = now_utc() + timedelta(hours=8)
    arr = dep + timedelta(hours=2, minutes=45)

    result = service.create_trip(db_session, driver, base_trip_data(
        departure_time=dep,
        estimated_duration_minutes=165,
        estimated_arrival_time=arr,
    ))
    db_session.commit()

    assert result["estimated_duration_minutes"] == 165
    assert result["estimated_arrival_time"] == arr


# ── Gap #7: Title / salutation ────────────────────────────────────────────────


def test_user_title_field(db_session):
    repo = UserRepository()
    user = repo.create(db_session, User(
        title="Mr.",
        first_name="John", last_name="Doe",
        email="mr-john@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.PASSENGER, is_email_verified=True,
    ))
    db_session.commit()

    assert user.title == "Mr."


def test_user_title_in_public_response(db_session):
    repo = UserRepository()
    user = repo.create(db_session, User(
        title="Dr.",
        first_name="Jane", last_name="Smith",
        email="dr-jane@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.PASSENGER, is_email_verified=True,
    ))
    db_session.commit()

    resp = UserPublicResponse.model_validate(user)
    assert resp.title == "Dr."


# ── Gap #8: Stops / waypoints ─────────────────────────────────────────────────


def test_trip_stores_stops(db_session):
    driver = make_driver(db_session, "stops-driver@example.com")
    trip_repo = TripRepository()
    service = TripService(trip_repo)

    stops = [
        {"address": "Ibadan", "lat": 7.3775, "lng": 3.9470},
        {"address": "Ogbomosho", "lat": 8.1374, "lng": 4.2419},
    ]
    result = service.create_trip(db_session, driver, base_trip_data(stops=stops))
    db_session.commit()

    assert len(result["stops"]) == 2
    assert result["stops"][0]["address"] == "Ibadan"


# ── Gap #9: Search sorting ────────────────────────────────────────────────────


def test_search_sort_by_price_asc(db_session):
    driver = make_driver(db_session, "sort-driver@example.com")
    trip_repo = TripRepository()
    service = TripService(trip_repo)

    service.create_trip(db_session, driver, base_trip_data(price_per_seat=50, origin_city="Lagos"))
    service.create_trip(db_session, driver, base_trip_data(price_per_seat=10, origin_city="Lagos"))
    service.create_trip(db_session, driver, base_trip_data(price_per_seat=30, origin_city="Lagos"))
    db_session.commit()

    results = service.search_trips(db_session, "Lagos", None, None, None, sort_by="price", order="asc")
    prices = [r["price_per_seat"] for r in results]
    assert prices == sorted(prices)


def test_search_sort_by_price_desc(db_session):
    driver = make_driver(db_session, "sort-desc-driver@example.com")
    trip_repo = TripRepository()
    service = TripService(trip_repo)

    service.create_trip(db_session, driver, base_trip_data(price_per_seat=50, origin_city="Kano"))
    service.create_trip(db_session, driver, base_trip_data(price_per_seat=10, origin_city="Kano"))
    db_session.commit()

    results = service.search_trips(db_session, "Kano", None, None, None, sort_by="price", order="desc")
    prices = [r["price_per_seat"] for r in results]
    assert prices == sorted(prices, reverse=True)


# ── Gap #10: Passport requirement ────────────────────────────────────────────


def test_trip_requires_passport_flag(db_session):
    driver = make_driver(db_session, "passport-driver@example.com")
    trip_repo = TripRepository()
    service = TripService(trip_repo)

    result = service.create_trip(db_session, driver, base_trip_data(requires_passport=True))
    db_session.commit()

    assert result["requires_passport"] is True


# ── Gap #11: Pending booking count per trip ───────────────────────────────────


def test_pending_booking_count_in_trip_response(db_session):
    driver = make_driver(db_session, "pending-cnt-driver@example.com")
    passenger = make_passenger(db_session, "pending-cnt-pax@example.com")
    trip_repo = TripRepository()
    booking_repo = BookingRepository()
    service = TripService(trip_repo)

    result = service.create_trip(db_session, driver, base_trip_data())
    db_session.commit()

    trip_id = result["id"]
    booking_repo.create(db_session, Booking(
        trip_id=trip_id,
        passenger_id=passenger.id,
        seats=1,
        status=BookingStatus.PENDING,
        total_amount=20,
    ))
    booking_repo.create(db_session, Booking(
        trip_id=trip_id,
        passenger_id=passenger.id,
        seats=1,
        status=BookingStatus.CONFIRMED,
        total_amount=20,
    ))
    db_session.commit()

    updated = service.get_trip(db_session, trip_id)
    assert updated["pending_booking_count"] == 1


# ── Gap #12: is_verified computed badge ──────────────────────────────────────


def test_is_verified_false_when_not_all_verified(db_session):
    repo = UserRepository()
    user = repo.create(db_session, User(
        first_name="Partial", last_name="Verify",
        email="partial-verify@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.PASSENGER,
        is_email_verified=True,
        is_phone_verified=False,
        identity_verified=False,
    ))
    db_session.commit()

    resp = UserPublicResponse.model_validate(user)
    assert resp.is_verified is False


def test_is_verified_true_when_all_verified(db_session):
    repo = UserRepository()
    user = repo.create(db_session, User(
        first_name="Fully", last_name="Verified",
        email="fully-verified@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.PASSENGER,
        is_email_verified=True,
        is_phone_verified=True,
        identity_verified=True,
    ))
    db_session.commit()

    resp = UserPublicResponse.model_validate(user)
    assert resp.is_verified is True


# ── Gap #13: trips_completed in public response ───────────────────────────────


def test_trips_completed_in_public_response(db_session):
    repo = UserRepository()
    user = repo.create(db_session, User(
        first_name="Active", last_name="Driver",
        email="active-driver@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.DRIVER, is_email_verified=True,
        trips_completed=120,
    ))
    db_session.commit()

    resp = UserPublicResponse.model_validate(user)
    assert resp.trips_completed == 120


# ── TripCreate schema validation for vehicle ──────────────────────────────────


def test_trip_create_schema_requires_vehicle_id_or_fields():
    with pytest.raises(Exception):
        TripCreate(
            origin_city="Lagos",
            destination_city="Abuja",
            departure_time=now_utc() + timedelta(hours=5),
            available_seats=3,
            price_per_seat=20,
        )


def test_trip_create_schema_accepts_vehicle_id(db_session):
    data = TripCreate(
        origin_city="Lagos",
        destination_city="Abuja",
        departure_time=now_utc() + timedelta(hours=5),
        available_seats=3,
        price_per_seat=20,
        vehicle_id="00000000-0000-0000-0000-000000000001",
    )
    assert data.vehicle_id is not None


def test_trip_create_schema_accepts_manual_vehicle_fields():
    data = TripCreate(
        origin_city="Lagos",
        destination_city="Abuja",
        departure_time=now_utc() + timedelta(hours=5),
        available_seats=3,
        price_per_seat=20,
        vehicle_make="Toyota",
        vehicle_model="Camry",
        vehicle_color="Black",
    )
    assert data.vehicle_make == "Toyota"


def test_trip_create_schema_accepts_booking_mode_only():
    data = TripCreate(
        origin_city="Lagos",
        destination_city="Abuja",
        departure_time=now_utc() + timedelta(hours=5),
        available_seats=3,
        price_per_seat=20,
        vehicle_make="Toyota",
        vehicle_model="Camry",
        vehicle_color="Black",
        booking_mode=BookingMode.INSTANT_BOOKING,
    )
    assert data.instant_booking is True
    assert data.booking_mode == BookingMode.INSTANT_BOOKING
