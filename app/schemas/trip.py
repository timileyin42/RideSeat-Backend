"""Trip schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.user import UserPublicResponse


class TripCreate(BaseModel):
    origin_city: str = Field(min_length=1, max_length=120)
    destination_city: str = Field(min_length=1, max_length=120)
    origin_address: str | None = Field(default=None, max_length=255)
    destination_address: str | None = Field(default=None, max_length=255)
    origin_lat: float | None = None
    origin_lng: float | None = None
    destination_lat: float | None = None
    destination_lng: float | None = None
    departure_time: datetime
    estimated_duration_minutes: int | None = Field(default=None, ge=1)
    estimated_arrival_time: datetime | None = None
    available_seats: int = Field(ge=1, le=6)
    price_per_seat: float = Field(gt=0)
    toll_fee: float = Field(default=0, ge=0)
    vehicle_id: UUID | None = None
    vehicle_make: str | None = Field(default=None, max_length=100)
    vehicle_model: str | None = Field(default=None, max_length=100)
    vehicle_color: str | None = Field(default=None, max_length=50)
    instant_booking: bool = False
    music_allowed: bool = False
    pets_allowed: bool = False
    smoking_allowed: bool = False
    air_conditioning: bool = False
    minimal_luggage: bool = False
    luggage_allowed: bool = False
    requires_passport: bool = False
    stops: list | None = None
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def check_vehicle(self) -> "TripCreate":
        has_id = self.vehicle_id is not None
        has_manual = self.vehicle_make and self.vehicle_model and self.vehicle_color
        if not has_id and not has_manual:
            raise ValueError("Provide vehicle_id or all of vehicle_make, vehicle_model, vehicle_color")
        return self


class TripUpdate(BaseModel):
    origin_city: str | None = Field(default=None, min_length=1, max_length=120)
    destination_city: str | None = Field(default=None, min_length=1, max_length=120)
    origin_address: str | None = Field(default=None, max_length=255)
    destination_address: str | None = Field(default=None, max_length=255)
    origin_lat: float | None = None
    origin_lng: float | None = None
    destination_lat: float | None = None
    destination_lng: float | None = None
    departure_time: datetime | None = None
    estimated_duration_minutes: int | None = Field(default=None, ge=1)
    estimated_arrival_time: datetime | None = None
    available_seats: int | None = Field(default=None, ge=1, le=6)
    price_per_seat: float | None = Field(default=None, gt=0)
    toll_fee: float | None = Field(default=None, ge=0)
    vehicle_id: UUID | None = None
    vehicle_make: str | None = Field(default=None, max_length=100)
    vehicle_model: str | None = Field(default=None, max_length=100)
    vehicle_color: str | None = Field(default=None, max_length=50)
    instant_booking: bool | None = None
    music_allowed: bool | None = None
    pets_allowed: bool | None = None
    smoking_allowed: bool | None = None
    air_conditioning: bool | None = None
    minimal_luggage: bool | None = None
    luggage_allowed: bool | None = None
    requires_passport: bool | None = None
    stops: list | None = None
    notes: str | None = Field(default=None, max_length=500)


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    driver: UserPublicResponse | None = None
    driver_id: UUID
    vehicle_id: UUID | None
    origin_city: str
    destination_city: str
    origin_address: str | None
    destination_address: str | None
    origin_lat: float | None
    origin_lng: float | None
    destination_lat: float | None
    destination_lng: float | None
    departure_time: datetime
    estimated_duration_minutes: int | None
    estimated_arrival_time: datetime | None
    available_seats: int
    seats_remaining: int
    price_per_seat: float
    toll_fee: float
    vehicle_make: str
    vehicle_model: str
    vehicle_color: str
    instant_booking: bool
    music_allowed: bool
    pets_allowed: bool
    smoking_allowed: bool
    air_conditioning: bool
    minimal_luggage: bool
    luggage_allowed: bool
    requires_passport: bool
    stops: list | None
    notes: str | None
    is_cancelled: bool
    pending_booking_count: int = 0
