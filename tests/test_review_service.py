from datetime import timedelta

from app.core.constants import BookingStatus
from app.core.security import hash_password
from app.models.booking import Booking
from app.models.trip import Trip
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.review_repo import ReviewRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.services.review_service import ReviewService
from app.utils.datetime import now_utc


def test_review_updates_user_rating(db_session):
    user_repo = UserRepository()
    trip_repo = TripRepository()
    booking_repo = BookingRepository()
    review_repo = ReviewRepository()
    service = ReviewService(review_repo, booking_repo, user_repo)

    driver = user_repo.create(
        db_session,
        User(
            first_name="Driver",
            last_name="Rating",
            email="driver-rating@example.com",
            password_hash=hash_password("pass1234"),
            is_email_verified=True,
        ),
    )
    passenger = user_repo.create(
        db_session,
        User(
            first_name="Passenger",
            last_name="Rating",
            email="passenger-rating@example.com",
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
            departure_time=now_utc() - timedelta(days=1),
            available_seats=2,
            price_per_seat=15,
            vehicle_make="Honda",
            vehicle_model="Civic",
            vehicle_color="Black",
            luggage_allowed=False,
        ),
    )
    booking_repo.create(
        db_session,
        Booking(
            trip_id=trip.id,
            passenger_id=passenger.id,
            seats=1,
            status=BookingStatus.COMPLETED,
            total_amount=15,
        ),
    )
    db_session.commit()

    service.create_review(db_session, passenger, trip.id, driver.id, 4, "Smooth ride")
    db_session.commit()

    refreshed_driver = user_repo.get_by_id(db_session, driver.id)
    assert refreshed_driver.rating_avg == 4
    assert refreshed_driver.rating_count == 1
