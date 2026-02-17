"""Trip schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPublicResponse


class TripCreate(BaseModel):
    origin_city: str = Field(min_length=1, max_length=120)
    destination_city: str = Field(min_length=1, max_length=120)
    departure_time: datetime
    available_seats: int = Field(ge=1, le=6)
    price_per_seat: float = Field(gt=0)
    toll_fee: float = Field(default=0, ge=0)
    vehicle_make: str = Field(min_length=1, max_length=100)
    vehicle_model: str = Field(min_length=1, max_length=100)
    vehicle_color: str = Field(min_length=1, max_length=50)
    luggage_allowed: bool = False
    notes: str | None = Field(default=None, max_length=500)


class TripUpdate(BaseModel):
    origin_city: str | None = Field(default=None, min_length=1, max_length=120)
    destination_city: str | None = Field(default=None, min_length=1, max_length=120)
    departure_time: datetime | None = None
    available_seats: int | None = Field(default=None, ge=1, le=6)
    price_per_seat: float | None = Field(default=None, gt=0)
    toll_fee: float | None = Field(default=None, ge=0)
    vehicle_make: str | None = Field(default=None, min_length=1, max_length=100)
    vehicle_model: str | None = Field(default=None, min_length=1, max_length=100)
    vehicle_color: str | None = Field(default=None, min_length=1, max_length=50)
    luggage_allowed: bool | None = None
    notes: str | None = Field(default=None, max_length=500)


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    driver: UserPublicResponse | None = None
    driver_id: UUID
    origin_city: str
    destination_city: str
    departure_time: datetime
    available_seats: int
    seats_remaining: int
    price_per_seat: float
    toll_fee: float
    vehicle_make: str
    vehicle_model: str
    vehicle_color: str
    luggage_allowed: bool
    notes: str | None
    is_cancelled: bool
