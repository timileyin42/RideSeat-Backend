"""User model."""

from datetime import datetime, timezone, date
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ChatPreference, Gender, LuggageSize, SmokingPreference, UserRole
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[str | None] = mapped_column(String(30), default=None)
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone_verification_token: Mapped[str | None] = mapped_column(String(255), default=None)
    phone_verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    profile_photo_url: Mapped[str | None] = mapped_column(String(500), default=None)
    payment_details: Mapped[str | None] = mapped_column(String(255), default=None)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.PASSENGER)
    bio: Mapped[str | None] = mapped_column(String(300), default=None)
    age_range: Mapped[str | None] = mapped_column(String(50), default=None)
    date_of_birth: Mapped[date | None] = mapped_column(Date, default=None)
    gender: Mapped[Gender | None] = mapped_column(Enum(Gender), default=None)
    smoking_preference: Mapped[SmokingPreference | None] = mapped_column(Enum(SmokingPreference), default=None)
    chat_preference: Mapped[ChatPreference | None] = mapped_column(Enum(ChatPreference), default=None)
    notify_push: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_sms: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_in_app: Mapped[bool] = mapped_column(Boolean, default=True)
    marketing_emails: Mapped[bool] = mapped_column(Boolean, default=False)
    vehicle_photo_url: Mapped[str | None] = mapped_column(String(500), default=None)
    vehicle_make: Mapped[str | None] = mapped_column(String(100), default=None)
    vehicle_model: Mapped[str | None] = mapped_column(String(100), default=None)
    vehicle_type: Mapped[str | None] = mapped_column(String(100), default=None)
    vehicle_color: Mapped[str | None] = mapped_column(String(50), default=None)
    vehicle_year: Mapped[int | None] = mapped_column(Integer, default=None)
    vehicle_plate: Mapped[str | None] = mapped_column(String(50), default=None)
    luggage_size: Mapped[LuggageSize | None] = mapped_column(Enum(LuggageSize), default=None)
    back_seat_max: Mapped[int | None] = mapped_column(Integer, default=None)
    has_winter_tires: Mapped[bool] = mapped_column(Boolean, default=False)
    allows_bikes: Mapped[bool] = mapped_column(Boolean, default=False)
    allows_skis: Mapped[bool] = mapped_column(Boolean, default=False)
    allows_snowboards: Mapped[bool] = mapped_column(Boolean, default=False)
    allows_pets: Mapped[bool] = mapped_column(Boolean, default=False)
    rating_avg: Mapped[float] = mapped_column(Numeric(3, 2), default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    trips_completed: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verification_token: Mapped[str | None] = mapped_column(String(255), default=None)
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    password_reset_token: Mapped[str | None] = mapped_column(String(255), default=None)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    trips = relationship("Trip", back_populates="driver", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="passenger", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="sender", cascade="all, delete-orphan")
    reviews_written = relationship("Review", back_populates="reviewer", foreign_keys="Review.reviewer_id")
    reviews_received = relationship("Review", back_populates="reviewee", foreign_keys="Review.reviewee_id")
    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
