"""Payment schemas."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict

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


class ConnectOnboardResponse(BaseModel):
    account_id: str
    onboarding_url: str


class ConnectStatusResponse(BaseModel):
    connected: bool
    charges_enabled: bool
    payouts_enabled: bool
    account_id: str | None = None
