"""Messaging service."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.trip_repo import TripRepository


class MessageService:
    def __init__(
        self,
        message_repo: MessageRepository,
        booking_repo: BookingRepository,
        trip_repo: TripRepository,
    ) -> None:
        self.message_repo = message_repo
        self.booking_repo = booking_repo
        self.trip_repo = trip_repo

    def list_messages(self, db: Session, actor: User, booking_id: UUID) -> list[Message]:
        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking:
            raise ValueError("Booking not found")
        trip = self.trip_repo.get_by_id(db, booking.trip_id)
        if not trip:
            raise ValueError("Trip not found")
        if actor.id not in {booking.passenger_id, trip.driver_id}:
            raise ValueError("Not allowed to access messages")
        return self.message_repo.list_by_booking(db, booking_id)

    def send_message(self, db: Session, actor: User, booking_id: UUID, content: str) -> Message:
        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking:
            raise ValueError("Booking not found")
        trip = self.trip_repo.get_by_id(db, booking.trip_id)
        if not trip:
            raise ValueError("Trip not found")
        if actor.id not in {booking.passenger_id, trip.driver_id}:
            raise ValueError("Not allowed to send messages")
        message = Message(booking_id=booking_id, sender_id=actor.id, content=content)
        return self.message_repo.create(db, message)
