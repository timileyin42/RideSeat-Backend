"""Device schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import DevicePlatform


class DeviceRegistrationRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "device_token": "fXmT3kL9pQ:APA91bHZ...",
            "platform": "ANDROID",
            "device_name": "Samsung Galaxy S24",
            "app_version": "1.0.0",
        }
    })

    device_token: str = Field(min_length=1, max_length=500)
    platform: DevicePlatform
    device_name: str | None = Field(default=None, max_length=120)
    app_version: str | None = Field(default=None, max_length=50)


class DeviceTokenUpdateRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "old_device_token": "fXmT3kL9pQ:APA91bHZ...",
            "new_device_token": "gYnU4mM0qR:APA91bIA...",
            "platform": "ANDROID",
            "device_name": "Samsung Galaxy S24",
            "app_version": "1.1.0",
        }
    })

    old_device_token: str = Field(min_length=1, max_length=500)
    new_device_token: str = Field(min_length=1, max_length=500)
    platform: DevicePlatform | None = None
    device_name: str | None = Field(default=None, max_length=120)
    app_version: str | None = Field(default=None, max_length=50)


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_token: str
    platform: DevicePlatform
    device_name: str | None
    app_version: str | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
