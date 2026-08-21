"""Contact form route."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core.dependencies import rate_limit
from app.schemas.base import DataResponse
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)
router = APIRouter()
email_service = EmailService()


class ContactRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    message: str = Field(..., min_length=10, max_length=2000)


@router.post("", response_model=DataResponse[dict])
def submit_contact_form(
    payload: ContactRequest,
    _=Depends(rate_limit("contact_form", limit=5, window_seconds=3600)),
):
    """Public contact form — 5 submissions per IP per hour."""
    try:
        email_service.send_contact_message(payload.name, payload.email, payload.message)
        return DataResponse(data={"sent": True})
    except Exception as exc:
        logger.error("Contact form email failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to send message. Please try again later.") from exc
