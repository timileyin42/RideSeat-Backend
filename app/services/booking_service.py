"""Booking service."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import BookingStatus, NotificationType
from app.models.booking import Booking
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
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
        notification_service: NotificationService,
        payment_service: PaymentService,
    ) -> None:
        self.booking_repo = booking_repo
        self.trip_repo = trip_repo
        self.user_repo = user_repo
        self.email_service = email_service
        self.notification_service = notification_service
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
            self.notification_service.create_notification(
                db,
                passenger.id,
                NotificationType.TRIP_COMPLETED,
                "Trip completed",
                f"Your trip from {trip.origin_city} to {trip.destination_city} is completed.",
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
            self.notification_service.create_notification(
                db,
                driver.id,
                NotificationType.TRIP_COMPLETED,
                "Trip completed",
                f"Your trip from {trip.origin_city} to {trip.destination_city} is completed.",
            )
        self.payment_service.trigger_payout_background(booking.id)

    def _handle_cancellation(self, db: Session, booking: Booking, trip, actor: User) -> None:
        self.payment_service.refund_for_cancellation(db, booking.id, trip.departure_time)
        passenger = self.user_repo.get_by_id(db, booking.passenger_id)
        driver = self.user_repo.get_by_id(db, trip.driver_id)
        if actor.id == booking.passenger_id and driver:
            self.notification_service.create_notification(
                db,
                driver.id,
                NotificationType.BOOKING_CANCELLED,
                "Booking cancelled",
                f"A booking for your trip from {trip.origin_city} to {trip.destination_city} was cancelled.",
            )
        if actor.id == trip.driver_id and passenger:
            self.notification_service.create_notification(
                db,
                passenger.id,
                NotificationType.BOOKING_CANCELLED,
                "Booking cancelled",
                f"Your booking for the trip from {trip.origin_city} to {trip.destination_city} was cancelled.",
            )

    def _handle_admin_cancellation(self, db: Session, booking: Booking, trip) -> None:
        passenger = self.user_repo.get_by_id(db, booking.passenger_id)
        driver = self.user_repo.get_by_id(db, trip.driver_id)
        if passenger:
            self.notification_service.create_notification(
                db,
                passenger.id,
                NotificationType.BOOKING_CANCELLED,
                "Booking cancelled",
                f"Your booking for the trip from {trip.origin_city} to {trip.destination_city} was cancelled.",
            )
        if driver:
            self.notification_service.create_notification(
                db,
                driver.id,
                NotificationType.BOOKING_CANCELLED,
                "Booking cancelled",
                f"A booking for your trip from {trip.origin_city} to {trip.destination_city} was cancelled.",
            )

    def _handle_rejection(self, db: Session, booking: Booking, trip) -> None:
        passenger = self.user_repo.get_by_id(db, booking.passenger_id)
        if passenger:
            self.notification_service.create_notification(
                db,
                passenger.id,
                NotificationType.BOOKING_CANCELLED,
                "Booking rejected",
                f"Your booking request for the trip from {trip.origin_city} to {trip.destination_city} was rejected.",
            )

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
        instant = getattr(trip, "instant_booking", False)
        status = BookingStatus.PENDING_PAYMENT if instant else BookingStatus.PENDING
        payment_deadline = now_utc() + timedelta(minutes=30) if instant else None
        booking = Booking(
            trip_id=trip.id,
            passenger_id=passenger.id,
            seats=seats,
            status=status,
            total_amount=total_amount,
            payment_deadline=payment_deadline,
        )
        created = self.booking_repo.create(db, booking)
        driver = self.user_repo.get_by_id(db, trip.driver_id)
        if instant:
            # Seat is held; confirmation fires after payment succeeds (via webhook)
            self.notification_service.create_notification(
                db,
                passenger.id,
                NotificationType.BOOKING_REQUEST,
                "Complete your payment",
                f"Your seat from {trip.origin_city} to {trip.destination_city} is reserved. Complete payment to confirm.",
            )
        else:
            if driver:
                self.email_service.send_booking_request_email(
                    driver.email,
                    driver.first_name or "Driver",
                    passenger.first_name or "Passenger",
                    trip.origin_city,
                    trip.destination_city,
                    trip.departure_time.isoformat(),
                )
                self.notification_service.create_notification(
                    db,
                    driver.id,
                    NotificationType.BOOKING_REQUEST,
                    "New booking request",
                    f"{passenger.first_name or 'Passenger'} requested a seat from {trip.origin_city} to {trip.destination_city}.",
                )
        return created

    def list_bookings(self, db: Session, passenger: User) -> list[Booking]:
        return self.booking_repo.list_by_user(db, passenger.id)

    def list_bookings_for_driver(
        self,
        db: Session,
        driver: User,
        status: BookingStatus | None = None,
    ) -> list[Booking]:
        return self.booking_repo.list_by_driver(db, driver.id, status=status)

    def list_bookings_for_trip(
        self,
        db: Session,
        driver: User,
        trip_id: UUID,
        status: BookingStatus | None = None,
    ) -> list[Booking]:
        trip = self.trip_repo.get_by_id(db, trip_id)
        if not trip:
            raise ValueError("Trip not found")
        if trip.driver_id != driver.id:
            raise ValueError("Only the trip driver can view bookings for this trip")
        return self.booking_repo.list_by_trip_and_status(db, trip_id, status=status)

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
        if status == BookingStatus.REJECTED:
            if trip.driver_id != actor.id:
                raise ValueError("Only driver can reject booking")
            if booking.status != BookingStatus.PENDING:
                raise ValueError("Can only reject pending bookings")

        # Driver approving a review-required booking → hold for payment first.
        # Deadline: 2 hours if departure is >48 hours away, else 30 minutes.
        if status == BookingStatus.CONFIRMED and booking.status == BookingStatus.PENDING:
            hours_to_departure = (ensure_utc(trip.departure_time) - now_utc()).total_seconds() / 3600
            payment_window = timedelta(hours=2) if hours_to_departure > 48 else timedelta(minutes=30)
            booking.status = BookingStatus.PENDING_PAYMENT
            booking.payment_deadline = now_utc() + payment_window
            self.booking_repo.update(db, booking)
            window_str = "2 hours" if hours_to_departure > 48 else "30 minutes"
            self.notification_service.create_notification(
                db,
                booking.passenger_id,
                NotificationType.BOOKING_REQUEST,
                "Your booking was approved — complete payment",
                f"Your seat from {trip.origin_city} to {trip.destination_city} has been approved. Complete payment within {window_str} to confirm your spot.",
                data={"booking_id": str(booking.id), "trip_id": str(trip.id)},
            )
            return booking

        booking.status = status
        updated = self.booking_repo.update(db, booking)
        if status == BookingStatus.COMPLETED:
            self._handle_completion(db, booking, trip)
        if status == BookingStatus.CANCELLED:
            self._handle_cancellation(db, booking, trip, actor)
        if status == BookingStatus.REJECTED:
            self._handle_rejection(db, booking, trip)
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
        if status == BookingStatus.CANCELLED:
            self._handle_admin_cancellation(db, booking, trip)
        return updated

    def confirm_booking_after_payment(self, db: Session, booking_id: UUID) -> Booking:
        """Called by payment webhook after payment_intent.succeeded."""
        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking or booking.status != BookingStatus.PENDING_PAYMENT:
            return booking
        booking.status = BookingStatus.CONFIRMED
        updated = self.booking_repo.update(db, booking)
        trip = self.trip_repo.get_by_id(db, booking.trip_id)
        passenger = self.user_repo.get_by_id(db, booking.passenger_id)
        driver = self.user_repo.get_by_id(db, trip.driver_id) if trip else None
        origin = trip.origin_city if trip else "origin"
        destination = trip.destination_city if trip else "destination"
        if passenger:
            self.notification_service.create_notification(
                db, passenger.id, NotificationType.BOOKING_REQUEST,
                "Booking confirmed",
                f"Payment received. Your seat from {origin} to {destination} is confirmed.",
            )
        if driver:
            self.notification_service.create_notification(
                db, driver.id, NotificationType.BOOKING_REQUEST,
                "New booking",
                f"{passenger.first_name if passenger else 'A passenger'} has paid and booked a seat from {origin} to {destination}.",
            )
        return updated

    def cancel_expired_pending_payments(self, db: Session) -> int:
        """Cancel PENDING_PAYMENT bookings whose payment_deadline has passed."""
        expired = self.booking_repo.list_expired_pending_payments(db, now_utc())
        count = 0
        for booking in expired:
            booking.status = BookingStatus.CANCELLED
            self.booking_repo.update(db, booking)
            trip = self.trip_repo.get_by_id(db, booking.trip_id)
            origin = trip.origin_city if trip else "origin"
            destination = trip.destination_city if trip else "destination"
            # Notify passenger their seat was released
            self.notification_service.create_notification(
                db,
                booking.passenger_id,
                NotificationType.BOOKING_CANCELLED,
                "Booking cancelled — payment not received",
                f"Your seat from {origin} to {destination} was released because payment wasn't completed in time.",
                data={"booking_id": str(booking.id), "trip_id": str(booking.trip_id)},
            )
            # Notify driver the request is off
            if trip:
                self.notification_service.create_notification(
                    db,
                    trip.driver_id,
                    NotificationType.BOOKING_CANCELLED,
                    "Booking request expired",
                    f"A passenger didn't complete payment for their seat from {origin} to {destination}. The request has been removed.",
                    data={"booking_id": str(booking.id), "trip_id": str(booking.trip_id)},
                )
            count += 1
        return count

    def cancel_booking(self, db: Session, actor: User, booking_id: UUID) -> Booking:
        return self.update_status(db, actor, booking_id, BookingStatus.CANCELLED)
