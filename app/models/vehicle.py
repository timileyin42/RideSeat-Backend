"""Vehicle model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    make: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    type: Mapped[str | None] = mapped_column(String(100), default=None)
    color: Mapped[str] = mapped_column(String(50))
    year: Mapped[int | None] = mapped_column(Integer, default=None)
    plate: Mapped[str] = mapped_column(String(50))
    back_seat_max: Mapped[int | None] = mapped_column(Integer, default=None)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="vehicles")
    trips = relationship("Trip", back_populates="vehicle")
