"""Payment schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.constants import PaymentStatus


class PaymentIntentCreate(BaseModel):
    booking_id: str


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_id: str
    amount: float
    platform_fee: float
    payout_amount: float
    status: PaymentStatus
    stripe_payment_intent_id: str | None
    stripe_transfer_id: str | None
    created_at: datetime
