"""Trip repository."""

from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.booking import Booking
from app.models.trip import Trip
from app.core.constants import BookingStatus


class TripRepository:
    def get_by_id(self, db: Session, trip_id: UUID) -> Trip | None:
        stmt = select(Trip).options(selectinload(Trip.driver)).where(Trip.id == trip_id)
        return db.execute(stmt).scalar_one_or_none()

    def get_by_id_for_update(self, db: Session, trip_id: UUID) -> Trip | None:
        stmt = select(Trip).where(Trip.id == trip_id).with_for_update()
        return db.execute(stmt).scalar_one_or_none()

    def create(self, db: Session, trip: Trip) -> Trip:
        db.add(trip)
        db.flush()
        return trip

    def update(self, db: Session, trip: Trip) -> Trip:
        db.add(trip)
        db.flush()
        return trip

    def list_trips(self, db: Session, limit: int = 50, offset: int = 0) -> list[Trip]:
        stmt = select(Trip).options(selectinload(Trip.driver)).offset(offset).limit(limit)
        return list(db.execute(stmt).scalars().all())

    def count_trips(self, db: Session) -> int:
        stmt = select(func.count(Trip.id))
        return int(db.execute(stmt).scalar_one())

    def count_created_since(self, db: Session, since: datetime) -> int:
        stmt = select(func.count(Trip.id)).where(Trip.created_at >= since)
        return int(db.execute(stmt).scalar_one())

    def search(
        self,
        db: Session,
        origin_city: str | None,
        destination_city: str | None,
        departure_date: date | None,
        passengers: int | None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Trip]:
        stmt = select(Trip).options(selectinload(Trip.driver)).where(Trip.is_cancelled.is_(False))
        confirmed_seats = (
            select(func.coalesce(func.sum(Booking.seats), 0))
            .where(Booking.trip_id == Trip.id, Booking.status == BookingStatus.CONFIRMED)
            .scalar_subquery()
        )
        if origin_city:
            stmt = stmt.where(Trip.origin_city.ilike(f"%{origin_city}%"))
        if destination_city:
            stmt = stmt.where(Trip.destination_city.ilike(f"%{destination_city}%"))
        if departure_date:
            start = datetime.combine(departure_date, time.min)
            end = datetime.combine(departure_date, time.max)
            stmt = stmt.where(Trip.departure_time.between(start, end))
        if passengers:
            stmt = stmt.where(Trip.available_seats - confirmed_seats >= passengers)
        stmt = stmt.order_by(Trip.departure_time).offset(offset).limit(limit)
        return list(db.execute(stmt).scalars().all())

    def count_confirmed_seats(self, db: Session, trip_id: UUID) -> int:
        stmt = select(func.coalesce(func.sum(Booking.seats), 0)).where(
            Booking.trip_id == trip_id,
            Booking.status == BookingStatus.CONFIRMED,
        )
        return int(db.execute(stmt).scalar_one())
