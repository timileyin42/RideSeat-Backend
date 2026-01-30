from datetime import timedelta

import pytest

from app.core.constants import BookingStatus
from app.core.security import hash_password
from app.models.booking import Booking
from app.models.trip import Trip
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.services.message_service import MessageService
from app.utils.datetime import now_utc


def test_send_and_list_messages(db_session):
    user_repo = UserRepository()
    trip_repo = TripRepository()
    booking_repo = BookingRepository()
    message_repo = MessageRepository()
    service = MessageService(message_repo, booking_repo, trip_repo)

    driver = user_repo.create(
        db_session,
        User(
            first_name="Driver",
            last_name="Chat",
            email="driver-chat@example.com",
            password_hash=hash_password("pass1234"),
            is_email_verified=True,
        ),
    )
    passenger = user_repo.create(
        db_session,
        User(
            first_name="Passenger",
            last_name="Chat",
            email="passenger-chat@example.com",
            password_hash=hash_password("pass1234"),
            is_email_verified=True,
        ),
    )
    trip = trip_repo.create(
        db_session,
        Trip(
            driver_id=driver.id,
            origin_city="Lagos",
            destination_city="Ibadan",
            departure_time=now_utc() + timedelta(hours=2),
            available_seats=3,
            price_per_seat=10,
            vehicle_make="Toyota",
            vehicle_model="Corolla",
            vehicle_color="White",
            luggage_allowed=True,
        ),
    )
    booking = booking_repo.create(
        db_session,
        Booking(
            trip_id=trip.id,
            passenger_id=passenger.id,
            seats=1,
            status=BookingStatus.PENDING,
            total_amount=10,
        ),
    )
    db_session.commit()

    sent = service.send_message(db_session, passenger, booking.id, "Hello driver")
    db_session.commit()

    messages = service.list_messages(db_session, driver, booking.id)

    assert sent.content == "Hello driver"
    assert len(messages) == 1
    assert messages[0].sender_id == passenger.id


def test_send_message_rejects_non_participant(db_session):
    user_repo = UserRepository()
    trip_repo = TripRepository()
    booking_repo = BookingRepository()
    message_repo = MessageRepository()
    service = MessageService(message_repo, booking_repo, trip_repo)

    driver = user_repo.create(
        db_session,
        User(
            first_name="Driver",
            last_name="Chat",
            email="driver-chat-2@example.com",
            password_hash=hash_password("pass1234"),
            is_email_verified=True,
        ),
    )
    passenger = user_repo.create(
        db_session,
        User(
            first_name="Passenger",
            last_name="Chat",
            email="passenger-chat-2@example.com",
            password_hash=hash_password("pass1234"),
            is_email_verified=True,
        ),
    )
    intruder = user_repo.create(
        db_session,
        User(
            first_name="Intruder",
            last_name="Chat",
            email="intruder-chat@example.com",
            password_hash=hash_password("pass1234"),
            is_email_verified=True,
        ),
    )
    trip = trip_repo.create(
        db_session,
        Trip(
            driver_id=driver.id,
            origin_city="Abuja",
            destination_city="Kaduna",
            departure_time=now_utc() + timedelta(hours=3),
            available_seats=2,
            price_per_seat=12,
            vehicle_make="Honda",
            vehicle_model="Civic",
            vehicle_color="Black",
            luggage_allowed=False,
        ),
    )
    booking = booking_repo.create(
        db_session,
        Booking(
            trip_id=trip.id,
            passenger_id=passenger.id,
            seats=1,
            status=BookingStatus.PENDING,
            total_amount=12,
        ),
    )
    db_session.commit()

    with pytest.raises(ValueError):
        service.send_message(db_session, intruder, booking.id, "Hello")
