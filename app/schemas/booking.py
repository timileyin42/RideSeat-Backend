"""Booking schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import BookingStatus


class BookingCreate(BaseModel):
    trip_id: str
    seats: int = Field(ge=1, le=6)


class BookingStatusUpdate(BaseModel):
    status: BookingStatus


class BookingDisputeResolve(BaseModel):
    status: BookingStatus


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trip_id: UUID
    passenger_id: UUID
    seats: int
    status: BookingStatus
    total_amount: float
    created_at: datetime
