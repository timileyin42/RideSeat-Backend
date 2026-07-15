"""Payment schemas."""

from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import PaymentStatus


class PaymentIntentCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"booking_id": "c3d4e5f6-a7b8-9012-cdef-123456789012"}
    })
    booking_id: str


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_id: str
    amount: float
    platform_fee: float
    payout_amount: float
    status: PaymentStatus
    stripe_payment_intent_id: str | None = None
    stripe_client_secret: str | None = None
    stripe_transfer_id: str | None = None
    created_at: datetime


# --- Stripe Connect Custom ---

class ConnectAddress(BaseModel):
    line1: str
    city: str
    postal_code: str

class ConnectDOB(BaseModel):
    day: int = Field(ge=1, le=31)
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=1900, le=2010)

class ConnectOnboardRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "first_name": "James",
        "last_name": "Harrison",
        "dob": {"day": 15, "month": 6, "year": 1990},
        "address": {"line1": "12 Baker Street", "city": "London", "postal_code": "NW1 6XE"},
        "phone": "+447911123456",
        "account_holder_name": "James Harrison",
        "sort_code": "608371",
        "account_number": "12345678",
        "tos_accepted": True,
    }})

    first_name: str
    last_name: str
    dob: ConnectDOB
    address: ConnectAddress
    phone: str
    account_holder_name: str
    sort_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    account_number: str = Field(min_length=8, max_length=8, pattern=r"^\d{8}$")
    tos_accepted: bool


class ConnectOnboardResponse(BaseModel):
    account_id: str
    charges_enabled: bool
    payouts_enabled: bool


class ConnectDocumentResponse(BaseModel):
    file_id: str
    message: str


class ConnectStatusResponse(BaseModel):
    connected: bool
    charges_enabled: bool
    payouts_enabled: bool
    account_id: str | None = None


class PayoutRequestResponse(BaseModel):
    transfers_initiated: int
    total_amount: float
    message: str
