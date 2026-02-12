"""Device schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import DevicePlatform


class DeviceRegistrationRequest(BaseModel):
    device_token: str = Field(min_length=1, max_length=500)
    platform: DevicePlatform
    device_name: str | None = Field(default=None, max_length=120)
    app_version: str | None = Field(default=None, max_length=50)


class DeviceTokenUpdateRequest(BaseModel):
    old_device_token: str = Field(min_length=1, max_length=500)
    new_device_token: str = Field(min_length=1, max_length=500)
    platform: DevicePlatform | None = None
    device_name: str | None = Field(default=None, max_length=120)
    app_version: str | None = Field(default=None, max_length=50)


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_token: str
    platform: DevicePlatform
    device_name: str | None
    app_version: str | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
