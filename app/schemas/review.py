"""Review schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "trip_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "reviewee_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "rating": 5,
            "comment": "Fantastic driver — punctual, safe, and great conversation!",
        }
    })

    trip_id: str
    reviewee_id: str
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trip_id: str
    reviewer_id: str
    reviewee_id: str
    rating: int
    comment: str | None
    created_at: datetime
