"""Booking schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import BookingStatus


class DriverSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str | None = None
    last_name: str | None = None
    profile_photo_url: str | None = None
    rating_avg: float = 0
    rating_count: int = 0


class TripSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    origin_city: str
    destination_city: str
    departure_time: datetime
    driver: DriverSummary | None = None


class BookingCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "trip_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "seats": 2,
        }
    })

    trip_id: str
    seats: int = Field(ge=1, le=6)


class BookingStatusUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"status": "CONFIRMED"}
    })

    status: BookingStatus


class BookingDisputeResolve(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"status": "COMPLETED"}
    })

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
    trip: TripSummary | None = None
