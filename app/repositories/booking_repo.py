"""Booking repository."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import BookingStatus
from app.models.booking import Booking
from app.models.trip import Trip


class BookingRepository:
    def get_by_id(self, db: Session, booking_id: UUID) -> Booking | None:
        return db.get(Booking, booking_id)

    def list_by_user(self, db: Session, user_id: UUID) -> list[Booking]:
        stmt = select(Booking).where(Booking.passenger_id == user_id)
        return list(db.execute(stmt).scalars().all())

    def list_all(self, db: Session, limit: int = 50, offset: int = 0) -> list[Booking]:
        stmt = select(Booking).offset(offset).limit(limit)
        return list(db.execute(stmt).scalars().all())

    def count_by_status(self, db: Session, status: BookingStatus) -> int:
        stmt = select(func.count(Booking.id)).where(Booking.status == status)
        return int(db.execute(stmt).scalar_one())

    def count_all(self, db: Session) -> int:
        stmt = select(func.count(Booking.id))
        return int(db.execute(stmt).scalar_one())

    def count_repeat_users(self, db: Session) -> int:
        repeat_stmt = (
            select(Booking.passenger_id, func.count(Booking.id).label("booking_count"))
            .where(Booking.status == BookingStatus.COMPLETED)
            .group_by(Booking.passenger_id)
            .having(func.count(Booking.id) >= 2)
        )
        count_stmt = select(func.count()).select_from(repeat_stmt.subquery())
        return int(db.execute(count_stmt).scalar_one())

    def create(self, db: Session, booking: Booking) -> Booking:
        db.add(booking)
        db.flush()
        return booking

    def update(self, db: Session, booking: Booking) -> Booking:
        db.add(booking)
        db.flush()
        return booking

    def list_by_trip_and_status(self, db: Session, trip_id: UUID, status: BookingStatus) -> list[Booking]:
        stmt = select(Booking).where(Booking.trip_id == trip_id, Booking.status == status)
        return list(db.execute(stmt).scalars().all())

    def list_by_driver(self, db: Session, driver_id: UUID, status: BookingStatus | None = None) -> list[Booking]:
        stmt = select(Booking).join(Trip, Trip.id == Booking.trip_id).where(Trip.driver_id == driver_id)
        if status is not None:
            stmt = stmt.where(Booking.status == status)
        stmt = stmt.order_by(Booking.created_at.desc())
        return list(db.execute(stmt).scalars().all())

    def get_by_trip_and_passenger(self, db: Session, trip_id: UUID, passenger_id: UUID) -> Booking | None:
        stmt = select(Booking).where(Booking.trip_id == trip_id, Booking.passenger_id == passenger_id)
        return db.execute(stmt).scalar_one_or_none()

    def has_confirmed_booking_between(self, db: Session, driver_id: UUID, passenger_id: UUID) -> bool:
        stmt = (
            select(func.count(Booking.id))
            .join(Trip, Trip.id == Booking.trip_id)
            .where(
                Trip.driver_id == driver_id,
                Booking.passenger_id == passenger_id,
                Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.COMPLETED]),
            )
        )
        return int(db.execute(stmt).scalar_one()) > 0
