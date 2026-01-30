"""User schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.constants import UserRole


class UserBase(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone_number: str | None = Field(default=None, max_length=30)
    profile_photo_url: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None, max_length=300)
    age_range: str | None = Field(default=None, max_length=50)


class UserUpdate(UserBase):
    role: UserRole | None = None
    payment_details: str | None = Field(default=None, max_length=255)


class UserPublicResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: UserRole
    rating_avg: float
    rating_count: int
    trips_completed: int


class UserPrivateResponse(UserPublicResponse):
    email: EmailStr
    is_email_verified: bool
    payment_details: str | None
    created_at: datetime
