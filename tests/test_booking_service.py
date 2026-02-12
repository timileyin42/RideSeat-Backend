from datetime import timedelta

from app.core.constants import BookingStatus
from app.core.security import hash_password
from app.models.booking import Booking
from app.models.trip import Trip
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.services.booking_service import BookingService
from app.utils.datetime import now_utc


class StubEmailService:
    def __init__(self) -> None:
        self.completed_emails: list[str] = []

    def send_trip_completed_email(self, email: str, *args, **kwargs) -> None:
        self.completed_emails.append(email)

    def send_verification_email(self, *args, **kwargs) -> None:
        return None

    def send_password_reset_email(self, *args, **kwargs) -> None:
        return None


class StubPaymentService:
    def __init__(self) -> None:
        self.payouts: list[str] = []

    def trigger_payout_background(self, booking_id) -> None:
        self.payouts.append(str(booking_id))


class StubNotificationService:
    def __init__(self) -> None:
        self.notifications: list[tuple[str, str]] = []

    def create_notification(self, db_session, user_id, notification_type, title, body):
        self.notifications.append((str(user_id), title))


def test_complete_booking_sends_emails(db_session):
    user_repo = UserRepository()
    trip_repo = TripRepository()
    booking_repo = BookingRepository()
    email_service = StubEmailService()
    payment_service = StubPaymentService()
    notification_service = StubNotificationService()
    service = BookingService(booking_repo, trip_repo, user_repo, email_service, notification_service, payment_service)

    driver = user_repo.create(
        db_session,
        User(
            first_name="Driver",
            last_name="One",
            email="driver@example.com",
            password_hash=hash_password("pass1234"),
            is_email_verified=True,
        ),
    )
    passenger = user_repo.create(
        db_session,
        User(
            first_name="Passenger",
            last_name="Two",
            email="passenger@example.com",
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
            departure_time=now_utc() - timedelta(hours=2),
            available_seats=3,
            price_per_seat=20,
            vehicle_make="Toyota",
            vehicle_model="Corolla",
            vehicle_color="Blue",
            luggage_allowed=True,
        ),
    )
    booking = booking_repo.create(
        db_session,
        Booking(
            trip_id=trip.id,
            passenger_id=passenger.id,
            seats=1,
            status=BookingStatus.CONFIRMED,
            total_amount=20,
        ),
    )
    db_session.commit()

    service.update_status(db_session, driver, booking.id, BookingStatus.COMPLETED)
    db_session.commit()

    assert set(email_service.completed_emails) == {driver.email, passenger.email}
