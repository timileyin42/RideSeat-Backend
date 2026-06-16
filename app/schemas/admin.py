"""Admin schemas."""

from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID


class VerificationRejectRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "reason": "The licence image is blurry. Please resubmit a clear, well-lit photo.",
        }
    })

    reason: str | None = Field(default=None, max_length=500)


class AdminMetricsResponse(BaseModel):
    total_users: int
    total_trips: int
    confirmed_bookings: int
    total_revenue: float
    platform_fee_total: float
    trips_created_last_7_days: int
    booking_conversion_rate: float
    trip_completion_rate: float
    repeat_users: int
