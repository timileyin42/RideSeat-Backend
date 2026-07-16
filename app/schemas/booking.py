"""Booking schemas."""

from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import BookingStatus, TripStatus


class StopPoint(BaseModel):
    """A stop point along a trip route."""
    model_config = ConfigDict(from_attributes=True, json_schema_extra={
        "example": {
            "city": "Birmingham",
            "address": "Birmingham New Street Station",
            "lat": 52.4776,
            "lng": -1.8964,
            "stop_order": 1,
        }
    })

    city: str = Field(..., min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    lat: float | None = None
    lng: float | None = None
    stop_order: int = Field(..., ge=1, description="Order of the stop in the route, starting from 1")


class PassengerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str | None = None
    last_name: str | None = None
    profile_photo_url: str | None = None
    rating_avg: float = 0
    rating_count: int = 0


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
    origin_address: str | None = None
    destination_address: str | None = None
    departure_time: datetime
    available_seats: int
    price_per_seat: float
    trip_status: TripStatus = TripStatus.ACTIVE
    driver: DriverSummary | None = None
    stops: list[StopPoint] | None = None


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
    passenger: PassengerSummary | None = None
