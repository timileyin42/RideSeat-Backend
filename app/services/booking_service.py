"""Booking service."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import BookingStatus
from app.models.booking import Booking
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.services.email_service import EmailService
from app.services.payment_service import PaymentService
from app.utils.datetime import ensure_utc, now_utc
from app.utils.pagination import normalize_pagination


class BookingService:
    def __init__(
        self,
        booking_repo: BookingRepository,
        trip_repo: TripRepository,
        user_repo: UserRepository,
        email_service: EmailService,
        payment_service: PaymentService,
    ) -> None:
        self.booking_repo = booking_repo
        self.trip_repo = trip_repo
        self.user_repo = user_repo
        self.email_service = email_service
        self.payment_service = payment_service

    def _handle_completion(self, db: Session, booking: Booking, trip) -> None:
        passenger = self.user_repo.get_by_id(db, booking.passenger_id)
        driver = self.user_repo.get_by_id(db, trip.driver_id)
        departure_time = trip.departure_time.isoformat()
        if passenger:
            passenger.trips_completed += 1
            self.user_repo.update(db, passenger)
            self.email_service.send_trip_completed_email(
                passenger.email,
                passenger.first_name or "Passenger",
                trip.origin_city,
                trip.destination_city,
                departure_time,
            )
        if driver:
            driver.trips_completed += 1
            self.user_repo.update(db, driver)
            self.email_service.send_trip_completed_email(
                driver.email,
                driver.first_name or "Driver",
                trip.origin_city,
                trip.destination_city,
                departure_time,
            )
        self.payment_service.trigger_payout_background(booking.id)

    def create_booking(self, db: Session, passenger: User, trip_id: UUID, seats: int) -> Booking:
        trip = self.trip_repo.get_by_id_for_update(db, trip_id)
        if not trip or trip.is_cancelled:
            raise ValueError("Trip not found")
        if ensure_utc(trip.departure_time) <= now_utc():
            raise ValueError("Trip already departed")
        if trip.driver_id == passenger.id:
            raise ValueError("Driver cannot book own trip")
        confirmed_seats = self.trip_repo.count_confirmed_seats(db, trip.id)
        remaining = trip.available_seats - confirmed_seats
        if seats > remaining:
            raise ValueError("Not enough seats available")
        total_amount = float(trip.price_per_seat) * seats
        booking = Booking(
            trip_id=trip.id,
            passenger_id=passenger.id,
            seats=seats,
            status=BookingStatus.PENDING,
            total_amount=total_amount,
        )
        return self.booking_repo.create(db, booking)

    def list_bookings(self, db: Session, passenger: User) -> list[Booking]:
        return self.booking_repo.list_by_user(db, passenger.id)

    def list_all_bookings(self, db: Session, actor: User, limit: int | None = None, offset: int | None = None) -> list[Booking]:
        if not actor.is_admin:
            raise ValueError("Admin privileges required")
        pagination = normalize_pagination(limit, offset)
        return self.booking_repo.list_all(db, limit=pagination.limit, offset=pagination.offset)

    def update_status(self, db: Session, actor: User, booking_id: UUID, status: BookingStatus) -> Booking:
        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking:
            raise ValueError("Booking not found")
        if booking.status == status:
            return booking
        trip = self.trip_repo.get_by_id(db, booking.trip_id)
        if not trip:
            raise ValueError("Trip not found")
        if status == BookingStatus.CONFIRMED:
            if trip.driver_id != actor.id:
                raise ValueError("Only driver can confirm booking")
            confirmed_seats = self.trip_repo.count_confirmed_seats(db, trip.id)
            remaining = trip.available_seats - confirmed_seats
            if booking.seats > remaining:
                raise ValueError("Not enough seats available")
        if status == BookingStatus.CANCELLED:
            if actor.id not in {booking.passenger_id, trip.driver_id}:
                raise ValueError("Not allowed to cancel booking")
        if status == BookingStatus.COMPLETED:
            if trip.driver_id != actor.id:
                raise ValueError("Only driver can complete booking")
            if ensure_utc(trip.departure_time) > now_utc():
                raise ValueError("Cannot complete booking before trip departure")
        booking.status = status
        updated = self.booking_repo.update(db, booking)
        if status == BookingStatus.COMPLETED:
            self._handle_completion(db, booking, trip)
        return updated

    def resolve_dispute(self, db: Session, actor: User, booking_id: UUID, status: BookingStatus) -> Booking:
        if not actor.is_admin:
            raise ValueError("Admin privileges required")
        if status not in {BookingStatus.CANCELLED, BookingStatus.COMPLETED}:
            raise ValueError("Resolution status must be CANCELLED or COMPLETED")
        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking:
            raise ValueError("Booking not found")
        if booking.status == status:
            return booking
        trip = self.trip_repo.get_by_id(db, booking.trip_id)
        if not trip:
            raise ValueError("Trip not found")
        booking.status = status
        updated = self.booking_repo.update(db, booking)
        if status == BookingStatus.COMPLETED:
            self._handle_completion(db, booking, trip)
        return updated

    def cancel_booking(self, db: Session, actor: User, booking_id: UUID) -> Booking:
        return self.update_status(db, actor, booking_id, BookingStatus.CANCELLED)
