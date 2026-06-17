"""Shared constants and enums."""

from enum import StrEnum


class UserRole(StrEnum):
    DRIVER = "DRIVER"
    PASSENGER = "PASSENGER"
    BOTH = "BOTH"


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    NON_BINARY = "NON_BINARY"
    OTHER = "OTHER"
    PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY"


class SmokingPreference(StrEnum):
    SMOKING = "SMOKING"
    NO_SMOKING = "NO_SMOKING"


class ChatPreference(StrEnum):
    QUIET = "QUIET"
    OK_TO_CHAT = "OK_TO_CHAT"
    CHATTY = "CHATTY"


class LuggageSize(StrEnum):
    NO_LUGGAGE = "NO_LUGGAGE"
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"


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


class DevicePlatform(StrEnum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class NotificationType(StrEnum):
    BOOKING_REQUEST = "BOOKING_REQUEST"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    TRIP_COMPLETED = "TRIP_COMPLETED"
    MESSAGE_RECEIVED = "MESSAGE_RECEIVED"
    REVIEW_RECEIVED = "REVIEW_RECEIVED"


class IdentityVerificationStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TicketCategory(StrEnum):
    HARASSMENT = "HARASSMENT"
    FRAUD = "FRAUD"
    SAFETY = "SAFETY"
    MISCONDUCT = "MISCONDUCT"
    NO_SHOW = "NO_SHOW"
    PROPERTY_DAMAGE = "PROPERTY_DAMAGE"
    OTHER = "OTHER"


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


PLATFORM_FEE_PERCENT = 0.1
CURRENCY = "gbp"
