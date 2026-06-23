"""User schemas."""

from datetime import datetime, date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field

from app.core.constants import ChatPreference, Gender, IdentityVerificationStatus, LuggageSize, SmokingPreference, UserRole


class UserBase(BaseModel):
    title: str | None = Field(default=None, max_length=20)
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
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "first_name": "James",
            "last_name": "Harrison",
            "bio": "Friendly driver, love long road trips.",
            "gender": "MALE",
            "date_of_birth": "1992-06-15",
            "phone_number": "+447911123456",
            "smoking_preference": "NO_SMOKING",
            "chat_preference": "CHATTY",
            "notify_push": True,
            "notify_email": True,
        }
    })

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

    id: UUID
    role: UserRole
    rating_avg: float
    rating_count: int
    trips_completed: int
    is_email_verified: bool = False
    is_phone_verified: bool = False
    identity_verified: bool = False

    @computed_field
    @property
    def is_verified(self) -> bool:
        return self.is_email_verified and self.is_phone_verified and self.identity_verified


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
    selfie_url: str | None = None
    id_document_url: str | None = None
    driver_license_url: str | None = None
    driver_license_back_url: str | None = None
    driver_license_number: str | None = None
    identity_verification_status: IdentityVerificationStatus | None = None
    created_at: datetime


class OnboardingRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "first_name": "James",
            "last_name": "Harrison",
        }
    })

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class PhoneVerificationRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"code": "583017"}
    })

    code: str = Field(min_length=6, max_length=6)


class PhoneVerificationResponse(BaseModel):
    status: str
    channel: str  # "sms" | "whatsapp" | "voice" — tells the app which message to show


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
