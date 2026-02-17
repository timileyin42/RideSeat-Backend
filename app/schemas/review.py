"""Review schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
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
