"""Trip service."""

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import UserRole
from app.models.trip import Trip
from app.models.user import User
from app.repositories.trip_repo import TripRepository
from app.utils.pagination import normalize_pagination


class TripService:
    def __init__(self, trip_repo: TripRepository) -> None:
        self.trip_repo = trip_repo

    def get_trip(self, db: Session, trip_id: UUID) -> Trip:
        trip = self.trip_repo.get_by_id(db, trip_id)
        if not trip or trip.is_cancelled:
            raise ValueError("Trip not found")
        return trip

    def create_trip(self, db: Session, driver: User, data: dict) -> Trip:
        if driver.role not in {UserRole.DRIVER, UserRole.BOTH}:
            raise ValueError("Driver role required")
        if data["departure_time"] <= datetime.now(tz=timezone.utc):
            raise ValueError("Trip cannot be in the past")
        trip = Trip(driver_id=driver.id, **data)
        return self.trip_repo.create(db, trip)

    def update_trip(self, db: Session, driver: User, trip_id: UUID, updates: dict) -> Trip:
        trip = self.get_trip(db, trip_id)
        if trip.driver_id != driver.id:
            raise ValueError("Not allowed to update this trip")
        if "departure_time" in updates and updates["departure_time"]:
            if updates["departure_time"] <= datetime.now(tz=timezone.utc):
                raise ValueError("Trip cannot be in the past")
        if "available_seats" in updates and updates["available_seats"] is not None:
            confirmed_seats = self.trip_repo.count_confirmed_seats(db, trip.id)
            if updates["available_seats"] < confirmed_seats:
                raise ValueError("Cannot reduce seats below confirmed bookings")
        for key, value in updates.items():
            if value is not None:
                setattr(trip, key, value)
        return self.trip_repo.update(db, trip)

    def cancel_trip(self, db: Session, driver: User, trip_id: UUID) -> Trip:
        trip = self.get_trip(db, trip_id)
        if trip.driver_id != driver.id:
            raise ValueError("Not allowed to cancel this trip")
        trip.is_cancelled = True
        return self.trip_repo.update(db, trip)

    def search_trips(
        self,
        db: Session,
        origin_city: str | None,
        destination_city: str | None,
        departure_date: date | None,
        passengers: int | None,
    ) -> list[Trip]:
        return self.trip_repo.search(db, origin_city, destination_city, departure_date, passengers)

    def list_all_trips(self, db: Session, actor: User, limit: int | None = None, offset: int | None = None) -> list[Trip]:
        if not actor.is_admin:
            raise ValueError("Admin privileges required")
        pagination = normalize_pagination(limit, offset)
        return self.trip_repo.list_trips(db, limit=pagination.limit, offset=pagination.offset)
