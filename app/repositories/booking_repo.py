"""Booking repository."""

from uuid import UUID

from sqlalchemy import cast, Date, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.constants import BookingStatus
from app.models.booking import Booking
from app.models.trip import Trip
from app.models.user import User


class BookingRepository:
    def get_by_id(self, db: Session, booking_id: UUID) -> Booking | None:
        return db.get(Booking, booking_id)

    def list_by_user(self, db: Session, user_id: UUID) -> list[Booking]:
        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.trip).selectinload(Trip.driver),
                selectinload(Booking.passenger)
            )
            .where(Booking.passenger_id == user_id)
            .order_by(Booking.created_at.desc())
        )
        return list(db.execute(stmt).scalars().all())

    def list_all(self, db: Session, limit: int = 50, offset: int = 0) -> list[Booking]:
        stmt = select(Booking).offset(offset).limit(limit)
        return list(db.execute(stmt).scalars().all())

    def count_by_status(self, db: Session, status: BookingStatus, since=None) -> int:
        stmt = select(func.count(Booking.id)).where(Booking.status == status)
        if since is not None:
            stmt = stmt.where(Booking.created_at >= since)
        return int(db.execute(stmt).scalar_one())

    def count_all(self, db: Session, since=None) -> int:
        stmt = select(func.count(Booking.id))
        if since is not None:
            stmt = stmt.where(Booking.created_at >= since)
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

    def list_by_trip_and_status(self, db: Session, trip_id: UUID, status: BookingStatus | None = None) -> list[Booking]:
        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.trip).selectinload(Trip.driver),
                selectinload(Booking.passenger)
            )
            .where(Booking.trip_id == trip_id)
        )
        if status is not None:
            stmt = stmt.where(Booking.status == status)
        stmt = stmt.order_by(Booking.created_at.desc())
        return list(db.execute(stmt).scalars().all())

    def list_by_driver(self, db: Session, driver_id: UUID, status: BookingStatus | None = None) -> list[Booking]:
        stmt = (
            select(Booking)
            .join(Trip, Trip.id == Booking.trip_id)
            .options(
                selectinload(Booking.trip).selectinload(Trip.driver),
                selectinload(Booking.passenger)
            )
            .where(Trip.driver_id == driver_id)
        )
        if status is not None:
            stmt = stmt.where(Booking.status == status)
        stmt = stmt.order_by(Booking.created_at.desc())
        return list(db.execute(stmt).scalars().all())

    def get_by_trip_and_passenger(self, db: Session, trip_id: UUID, passenger_id: UUID) -> Booking | None:
        stmt = select(Booking).where(Booking.trip_id == trip_id, Booking.passenger_id == passenger_id)
        return db.execute(stmt).scalar_one_or_none()

    def list_by_status_before(self, db: Session, status: BookingStatus, before) -> list[Booking]:
        from datetime import datetime
        stmt = select(Booking).where(
            Booking.status == status,
            Booking.created_at < before,
        )
        return list(db.execute(stmt).scalars().all())

    def bookings_timeseries(self, db: Session, days: int = 7) -> list[dict]:
        """Daily booking count for the last N days."""
        from datetime import timedelta
        from app.utils.datetime import now_utc
        since = now_utc() - timedelta(days=days)
        stmt = (
            select(
                cast(Booking.created_at, Date).label("date"),
                func.count(Booking.id).label("value"),
            )
            .where(Booking.created_at >= since)
            .group_by(cast(Booking.created_at, Date))
            .order_by(cast(Booking.created_at, Date))
        )
        rows = db.execute(stmt).all()
        return [{"date": str(row.date), "value": int(row.value)} for row in rows]

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
