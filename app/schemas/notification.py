"""Notification schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import NotificationType


class SendNotificationRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "recipient_id": "861fbb9c-8b42-43cc-b2c3-94d4cae97319",
            "title": "Your trip is starting soon",
            "body": "Driver is on the way. Be ready in 5 minutes.",
        }
    })

    recipient_id: UUID
    title: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=1, max_length=500)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    notification_type: NotificationType
    title: str
    body: str
    is_read: bool
    created_at: datetime
