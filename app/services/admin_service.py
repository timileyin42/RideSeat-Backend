"""Admin service."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.constants import BookingStatus
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.utils.datetime import now_utc


class AdminService:
    def __init__(
        self,
        user_repo: UserRepository,
        trip_repo: TripRepository,
        booking_repo: BookingRepository,
        payment_repo: PaymentRepository,
    ) -> None:
        self.user_repo = user_repo
        self.trip_repo = trip_repo
        self.booking_repo = booking_repo
        self.payment_repo = payment_repo

    def get_metrics(self, db: Session, actor: User) -> dict:
        if not actor.is_admin:
            raise ValueError("Admin privileges required")
        total_users = self.user_repo.count_users(db)
        total_trips = self.trip_repo.count_trips(db)
        confirmed_bookings = self.booking_repo.count_by_status(db, BookingStatus.CONFIRMED)
        completed_bookings = self.booking_repo.count_by_status(db, BookingStatus.COMPLETED)
        total_bookings = self.booking_repo.count_all(db)
        total_revenue = self.payment_repo.sum_total_revenue(db)
        platform_fee_total = self.payment_repo.sum_platform_fees(db)
        trips_created_last_7_days = self.trip_repo.count_created_since(db, now_utc() - timedelta(days=7))
        booking_conversion_rate = confirmed_bookings / total_bookings if total_bookings else 0.0
        trip_completion_rate = completed_bookings / confirmed_bookings if confirmed_bookings else 0.0
        repeat_users = self.booking_repo.count_repeat_users(db)
        return {
            "total_users": total_users,
            "total_trips": total_trips,
            "confirmed_bookings": confirmed_bookings,
            "total_revenue": total_revenue,
            "platform_fee_total": platform_fee_total,
            "trips_created_last_7_days": trips_created_last_7_days,
            "booking_conversion_rate": booking_conversion_rate,
            "trip_completion_rate": trip_completion_rate,
            "repeat_users": repeat_users,
        }
