"""User schemas."""

from datetime import datetime, date

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.constants import ChatPreference, Gender, LuggageSize, SmokingPreference, UserRole


class UserBase(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    profile_photo_url: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None, max_length=300)
    age_range: str | None = Field(default=None, max_length=50)
    date_of_birth: date | None = None
    gender: Gender | None = None
    smoking_preference: SmokingPreference | None = None
    chat_preference: ChatPreference | None = None
    vehicle_photo_url: str | None = Field(default=None, max_length=500)
    vehicle_make: str | None = Field(default=None, max_length=100)
    vehicle_model: str | None = Field(default=None, max_length=100)
    vehicle_type: str | None = Field(default=None, max_length=100)
    vehicle_color: str | None = Field(default=None, max_length=50)
    vehicle_year: int | None = Field(default=None, ge=1900, le=2100)
    vehicle_plate: str | None = Field(default=None, max_length=50)
    luggage_size: LuggageSize | None = None
    back_seat_max: int | None = Field(default=None, ge=2, le=3)
    has_winter_tires: bool | None = None
    allows_bikes: bool | None = None
    allows_skis: bool | None = None
    allows_snowboards: bool | None = None
    allows_pets: bool | None = None


class UserUpdate(UserBase):
    role: UserRole | None = None
    payment_details: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=30)
    notify_push: bool | None = None
    notify_sms: bool | None = None
    notify_email: bool | None = None
    notify_in_app: bool | None = None
    marketing_emails: bool | None = None


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
    phone_number: str | None
    is_phone_verified: bool
    notify_push: bool
    notify_sms: bool
    notify_email: bool
    notify_in_app: bool
    marketing_emails: bool
    created_at: datetime


class PhoneVerificationRequest(BaseModel):
    code: str = Field(min_length=4, max_length=10)


class PhoneVerificationResponse(BaseModel):
    status: str
    code: str


class PhoneNumberResponse(BaseModel):
    phone_number: str


class PlaylistResponse(BaseModel):
    url: str


class PromoItem(BaseModel):
    title: str
    description: str
    promo_type: str
    code: str | None = None


class PromoListResponse(BaseModel):
    items: list[PromoItem]


class ReferralResponse(BaseModel):
    url: str
