"""Trip model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    driver_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    vehicle_id: Mapped[UUID | None] = mapped_column(ForeignKey("vehicles.id"), index=True, default=None)
    origin_city: Mapped[str] = mapped_column(String(120))
    destination_city: Mapped[str] = mapped_column(String(120))
    origin_address: Mapped[str | None] = mapped_column(String(255), default=None)
    destination_address: Mapped[str | None] = mapped_column(String(255), default=None)
    origin_lat: Mapped[float | None] = mapped_column(Float, default=None)
    origin_lng: Mapped[float | None] = mapped_column(Float, default=None)
    destination_lat: Mapped[float | None] = mapped_column(Float, default=None)
    destination_lng: Mapped[float | None] = mapped_column(Float, default=None)
    departure_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, default=None)
    estimated_arrival_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    available_seats: Mapped[int] = mapped_column(Integer)
    price_per_seat: Mapped[float] = mapped_column(Numeric(10, 2))
    toll_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    vehicle_make: Mapped[str] = mapped_column(String(100))
    vehicle_model: Mapped[str] = mapped_column(String(100))
    vehicle_color: Mapped[str] = mapped_column(String(50))
    instant_booking: Mapped[bool] = mapped_column(Boolean, default=False)
    music_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    pets_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    smoking_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    air_conditioning: Mapped[bool] = mapped_column(Boolean, default=False)
    minimal_luggage: Mapped[bool] = mapped_column(Boolean, default=False)
    luggage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_passport: Mapped[bool] = mapped_column(Boolean, default=False)
    stops: Mapped[list | None] = mapped_column(JSON, default=None)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    trip_status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    driver = relationship("User", back_populates="trips")
    vehicle = relationship("Vehicle", back_populates="trips")
    bookings = relationship("Booking", back_populates="trip", cascade="all, delete-orphan")
