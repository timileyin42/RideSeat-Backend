"""Notification schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import NotificationType


class SendNotificationRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "recipient_id": "861fbb9c-8b42-43cc-b2c3-94d4cae97319",
            "title": "New message from James",
            "body": "Hey, I'm 5 minutes away!",
            "notification_type": "CHAT",
            "data": {
                "trip_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "booking_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "other_user_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
            },
        }
    })

    recipient_id: UUID
    title: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=1, max_length=500)
    notification_type: NotificationType = NotificationType.GENERAL
    data: dict[str, str] | None = None


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    notification_type: NotificationType
    title: str
    body: str
    is_read: bool
    data: dict | None = None
    created_at: datetime
