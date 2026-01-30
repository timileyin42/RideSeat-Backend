"""Message schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_id: str
    sender_id: str
    content: str
    created_at: datetime
