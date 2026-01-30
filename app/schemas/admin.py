"""Admin schemas."""

from pydantic import BaseModel


class AdminMetricsResponse(BaseModel):
    total_users: int
    total_trips: int
    confirmed_bookings: int
    total_revenue: float
    platform_fee_total: float
