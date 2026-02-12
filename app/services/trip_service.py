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

    def get_trip(self, db: Session, trip_id: UUID) -> dict:
        trip = self.trip_repo.get_by_id(db, trip_id)
        if not trip or trip.is_cancelled:
            raise ValueError("Trip not found")
        return self._to_response(db, trip)

    def create_trip(self, db: Session, driver: User, data: dict) -> dict:
        if driver.role not in {UserRole.DRIVER, UserRole.BOTH}:
            raise ValueError("Driver role required")
        if data["departure_time"] <= datetime.now(tz=timezone.utc):
            raise ValueError("Trip cannot be in the past")
        trip = Trip(driver_id=driver.id, **data)
        created = self.trip_repo.create(db, trip)
        return self._to_response(db, created)

    def update_trip(self, db: Session, driver: User, trip_id: UUID, updates: dict) -> dict:
        trip = self.trip_repo.get_by_id(db, trip_id)
        if not trip or trip.is_cancelled:
            raise ValueError("Trip not found")
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
        updated = self.trip_repo.update(db, trip)
        return self._to_response(db, updated)

    def cancel_trip(self, db: Session, driver: User, trip_id: UUID) -> dict:
        trip = self.trip_repo.get_by_id(db, trip_id)
        if not trip or trip.is_cancelled:
            raise ValueError("Trip not found")
        if trip.driver_id != driver.id:
            raise ValueError("Not allowed to cancel this trip")
        trip.is_cancelled = True
        updated = self.trip_repo.update(db, trip)
        return self._to_response(db, updated)

    def search_trips(
        self,
        db: Session,
        origin_city: str | None,
        destination_city: str | None,
        departure_date: date | None,
        passengers: int | None,
    ) -> list[dict]:
        trips = self.trip_repo.search(db, origin_city, destination_city, departure_date, passengers)
        return [self._to_response(db, trip) for trip in trips]

    def list_all_trips(self, db: Session, actor: User, limit: int | None = None, offset: int | None = None) -> list[dict]:
        if not actor.is_admin:
            raise ValueError("Admin privileges required")
        pagination = normalize_pagination(limit, offset)
        trips = self.trip_repo.list_trips(db, limit=pagination.limit, offset=pagination.offset)
        return [self._to_response(db, trip) for trip in trips]

    def _to_response(self, db: Session, trip: Trip) -> dict:
        confirmed_seats = self.trip_repo.count_confirmed_seats(db, trip.id)
        seats_remaining = max(trip.available_seats - confirmed_seats, 0)
        return {
            "id": trip.id,
            "driver": trip.driver,
            "driver_id": trip.driver_id,
            "origin_city": trip.origin_city,
            "destination_city": trip.destination_city,
            "departure_time": trip.departure_time,
            "available_seats": trip.available_seats,
            "seats_remaining": seats_remaining,
            "price_per_seat": trip.price_per_seat,
            "toll_fee": trip.toll_fee,
            "vehicle_make": trip.vehicle_make,
            "vehicle_model": trip.vehicle_model,
            "vehicle_color": trip.vehicle_color,
            "luggage_allowed": trip.luggage_allowed,
            "notes": trip.notes,
            "is_cancelled": trip.is_cancelled,
        }
