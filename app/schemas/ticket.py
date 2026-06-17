"""Ticket schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import TicketCategory, TicketStatus


class TicketCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "category": "MISCONDUCT",
            "subject": "Driver was rude and drove dangerously",
            "description": "The driver was speeding on the M6 and used abusive language when I asked him to slow down.",
            "reported_user_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "trip_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        }
    })

    category: TicketCategory
    subject: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10, max_length=2000)
    reported_user_id: UUID | None = None
    trip_id: UUID | None = None


class TicketAdminUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "IN_PROGRESS",
            "admin_note": "We have contacted the driver and are investigating the complaint.",
        }
    })

    status: TicketStatus | None = None
    admin_note: str | None = Field(default=None, max_length=2000)


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reporter_id: UUID
    reported_user_id: UUID | None
    trip_id: UUID | None
    category: TicketCategory
    subject: str
    description: str
    status: TicketStatus
    admin_note: str | None
    resolved_by: UUID | None
    created_at: datetime
    updated_at: datetime
