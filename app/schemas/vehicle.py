"""Vehicle schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VehicleCreate(BaseModel):
    make: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    type: str | None = Field(default=None, max_length=100)
    color: str = Field(min_length=1, max_length=50)
    year: int | None = Field(default=None, ge=1900, le=2100)
    plate: str = Field(min_length=1, max_length=50)
    back_seat_max: int | None = Field(default=None, ge=2, le=3)
    is_default: bool = False


class VehicleUpdate(BaseModel):
    make: str | None = Field(default=None, min_length=1, max_length=100)
    model: str | None = Field(default=None, min_length=1, max_length=100)
    type: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, min_length=1, max_length=50)
    year: int | None = Field(default=None, ge=1900, le=2100)
    plate: str | None = Field(default=None, min_length=1, max_length=50)
    back_seat_max: int | None = Field(default=None, ge=2, le=3)
    is_default: bool | None = None


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    make: str
    model: str
    type: str | None
    color: str
    year: int | None
    plate: str
    back_seat_max: int | None
    is_default: bool
    created_at: datetime
