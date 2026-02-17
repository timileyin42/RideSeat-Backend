"""Admin schemas."""

from pydantic import BaseModel
from uuid import UUID

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
