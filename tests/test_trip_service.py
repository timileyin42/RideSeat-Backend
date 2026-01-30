from datetime import timedelta

import pytest

from app.core.constants import BookingStatus, UserRole
from app.core.security import hash_password
from app.models.booking import Booking
from app.models.trip import Trip
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.services.trip_service import TripService
from app.utils.datetime import now_utc


def test_create_trip_requires_driver_role(db_session):
    user_repo = UserRepository()
    trip_repo = TripRepository()
    service = TripService(trip_repo)

    passenger = user_repo.create(
        db_session,
        User(
            first_name="Passenger",
            last_name="Only",
            email="passenger-only@example.com",
            password_hash=hash_password("pass1234"),
            role=UserRole.PASSENGER,
            is_email_verified=True,
        ),
    )
    db_session.commit()

    data = {
        "origin_city": "Lagos",
        "destination_city": "Ibadan",
        "departure_time": now_utc() + timedelta(hours=2),
        "available_seats": 3,
        "price_per_seat": 20,
        "vehicle_make": "Toyota",
        "vehicle_model": "Corolla",
        "vehicle_color": "Blue",
        "luggage_allowed": True,
    }

    with pytest.raises(ValueError):
        service.create_trip(db_session, passenger, data)


def test_create_trip_rejects_past_departure(db_session):
    user_repo = UserRepository()
    trip_repo = TripRepository()
    service = TripService(trip_repo)

    driver = user_repo.create(
        db_session,
        User(
            first_name="Driver",
            last_name="Past",
            email="driver-past@example.com",
            password_hash=hash_password("pass1234"),
            role=UserRole.DRIVER,
            is_email_verified=True,
        ),
    )
    db_session.commit()

    data = {
        "origin_city": "Abuja",
        "destination_city": "Kaduna",
        "departure_time": now_utc() - timedelta(hours=1),
        "available_seats": 2,
        "price_per_seat": 15,
        "vehicle_make": "Honda",
        "vehicle_model": "Civic",
        "vehicle_color": "Black",
        "luggage_allowed": False,
    }

    with pytest.raises(ValueError):
        service.create_trip(db_session, driver, data)


def test_update_trip_cannot_reduce_below_confirmed(db_session):
    user_repo = UserRepository()
    trip_repo = TripRepository()
    booking_repo = BookingRepository()
    service = TripService(trip_repo)

    driver = user_repo.create(
        db_session,
        User(
            first_name="Driver",
            last_name="Seats",
            email="driver-seats@example.com",
            password_hash=hash_password("pass1234"),
            role=UserRole.DRIVER,
            is_email_verified=True,
        ),
    )
    passenger = user_repo.create(
        db_session,
        User(
            first_name="Passenger",
            last_name="Seats",
            email="passenger-seats@example.com",
            password_hash=hash_password("pass1234"),
            role=UserRole.PASSENGER,
            is_email_verified=True,
        ),
    )
    trip = trip_repo.create(
        db_session,
        Trip(
            driver_id=driver.id,
            origin_city="Lagos",
            destination_city="Ibadan",
            departure_time=now_utc() + timedelta(hours=4),
            available_seats=3,
            price_per_seat=10,
            vehicle_make="Toyota",
            vehicle_model="Corolla",
            vehicle_color="White",
            luggage_allowed=True,
        ),
    )
    booking_repo.create(
        db_session,
        Booking(
            trip_id=trip.id,
            passenger_id=passenger.id,
            seats=2,
            status=BookingStatus.CONFIRMED,
            total_amount=20,
        ),
    )
    db_session.commit()

    with pytest.raises(ValueError):
        service.update_trip(db_session, driver, trip.id, {"available_seats": 1})


def test_list_all_trips_requires_admin(db_session):
    user_repo = UserRepository()
    trip_repo = TripRepository()
    service = TripService(trip_repo)

    actor = user_repo.create(
        db_session,
        User(
            first_name="User",
            last_name="Regular",
            email="user-regular@example.com",
            password_hash=hash_password("pass1234"),
            role=UserRole.PASSENGER,
            is_email_verified=True,
        ),
    )
    db_session.commit()

    with pytest.raises(ValueError):
        service.list_all_trips(db_session, actor, limit=10, offset=0)
