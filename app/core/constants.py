"""Shared constants and enums."""

from enum import StrEnum


class UserRole(StrEnum):
    DRIVER = "DRIVER"
    PASSENGER = "PASSENGER"
    BOTH = "BOTH"


class BookingStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class PaymentStatus(StrEnum):
    REQUIRES_PAYMENT_METHOD = "REQUIRES_PAYMENT_METHOD"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ReviewRatingRange(StrEnum):
    MIN = "1"
    MAX = "5"


PLATFORM_FEE_PERCENT = 0.1
CURRENCY = "usd"
