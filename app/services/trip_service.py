"""Trip service."""

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import BookingMode, BookingStatus, TripStatus
from app.models.booking import Booking
from app.models.trip import Trip
from app.models.user import User
from app.repositories.trip_repo import TripRepository
from app.utils.datetime import ensure_utc, now_utc
from app.utils.pagination import normalize_pagination


class TripService:
    def __init__(self, trip_repo: TripRepository) -> None:
        self.trip_repo = trip_repo

    def get_trip(self, db: Session, trip_id: UUID) -> dict:
        trip = self.trip_repo.get_by_id(db, trip_id)
        if not trip:
            raise ValueError("Trip not found")
        return self._to_response(db, trip)

    def create_trip(self, db: Session, driver: User, data: dict) -> dict:
        data = self._normalize_booking_mode(data)
        if ensure_utc(data["departure_time"]) <= now_utc():
            raise ValueError("Trip cannot be in the past")
        trip = Trip(driver_id=driver.id, **data)
        created = self.trip_repo.create(db, trip)
        return self._to_response(db, created)

    def update_trip(self, db: Session, driver: User, trip_id: UUID, updates: dict) -> dict:
        updates = self._normalize_booking_mode(updates)
        trip = self.trip_repo.get_by_id(db, trip_id)
        if not trip or trip.is_cancelled:
            raise ValueError("Trip not found")
        if trip.driver_id != driver.id:
            raise ValueError("Not allowed to update this trip")
        if "departure_time" in updates and updates["departure_time"]:
            if ensure_utc(updates["departure_time"]) <= now_utc():
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

    def start_trip(self, db: Session, driver: User, trip_id: UUID) -> dict:
        trip = self.trip_repo.get_by_id(db, trip_id)
        if not trip or trip.is_cancelled:
            raise ValueError("Trip not found")
        if trip.driver_id != driver.id:
            raise ValueError("Not allowed to start this trip")
        if trip.trip_status != TripStatus.ACTIVE:
            raise ValueError(f"Trip cannot be started from status: {trip.trip_status}")
        trip.trip_status = TripStatus.STARTED
        trip.started_at = now_utc()
        updated = self.trip_repo.update(db, trip)
        return self._to_response(db, updated)

    def complete_trip(self, db: Session, driver: User, trip_id: UUID) -> dict:
        trip = self.trip_repo.get_by_id(db, trip_id)
        if not trip or trip.is_cancelled:
            raise ValueError("Trip not found")
        if trip.driver_id != driver.id:
            raise ValueError("Not allowed to complete this trip")
        if trip.trip_status != TripStatus.STARTED:
            raise ValueError(f"Trip cannot be completed from status: {trip.trip_status}")
        trip.trip_status = TripStatus.COMPLETED
        trip.completed_at = now_utc()
        # Mark all confirmed bookings as completed
        from sqlalchemy import select as _select
        confirmed = list(
            db.execute(
                _select(Booking).where(
                    Booking.trip_id == trip_id,
                    Booking.status == BookingStatus.CONFIRMED,
                )
            ).scalars().all()
        )
        for booking in confirmed:
            booking.status = BookingStatus.COMPLETED
            db.add(booking)
        db.flush()
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
        sort_by: str | None = None,
        order: str | None = None,
    ) -> list[dict]:
        trips = self.trip_repo.search(
            db, origin_city, destination_city, departure_date, passengers,
            sort_by=sort_by, order=order,
        )
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
        pending_count = self.trip_repo.count_pending_bookings(db, trip.id)
        booking_mode = BookingMode.INSTANT_BOOKING if trip.instant_booking else BookingMode.REVIEW_REQUESTS
        return {
            "id": trip.id,
            "driver": trip.driver,
            "driver_id": trip.driver_id,
            "vehicle_id": trip.vehicle_id,
            "origin_city": trip.origin_city,
            "destination_city": trip.destination_city,
            "origin_address": trip.origin_address,
            "destination_address": trip.destination_address,
            "origin_lat": trip.origin_lat,
            "origin_lng": trip.origin_lng,
            "destination_lat": trip.destination_lat,
            "destination_lng": trip.destination_lng,
            "departure_time": trip.departure_time,
            "estimated_duration_minutes": trip.estimated_duration_minutes,
            "estimated_arrival_time": trip.estimated_arrival_time,
            "available_seats": trip.available_seats,
            "seats_remaining": seats_remaining,
            "price_per_seat": trip.price_per_seat,
            "toll_fee": trip.toll_fee,
            "vehicle_make": trip.vehicle_make,
            "vehicle_model": trip.vehicle_model,
            "vehicle_color": trip.vehicle_color,
            "booking_mode": booking_mode,
            "instant_booking": trip.instant_booking,
            "music_allowed": trip.music_allowed,
            "pets_allowed": trip.pets_allowed,
            "smoking_allowed": trip.smoking_allowed,
            "air_conditioning": trip.air_conditioning,
            "minimal_luggage": trip.minimal_luggage,
            "luggage_allowed": trip.luggage_allowed,
            "requires_passport": trip.requires_passport,
            "stops": trip.stops,
            "notes": trip.notes,
            "is_cancelled": trip.is_cancelled,
            "trip_status": trip.trip_status,
            "started_at": trip.started_at,
            "completed_at": trip.completed_at,
            "pending_booking_count": pending_count,
        }

    def _normalize_booking_mode(self, data: dict) -> dict:
        normalized = dict(data)
        booking_mode = normalized.pop("booking_mode", None)
        if booking_mode is not None:
            normalized["instant_booking"] = booking_mode == BookingMode.INSTANT_BOOKING
        return normalized
