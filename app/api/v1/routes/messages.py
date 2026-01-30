"""Message routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db
from app.repositories.booking_repo import BookingRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.trip_repo import TripRepository
from app.schemas.message import MessageCreate, MessageResponse
from app.services.message_service import MessageService

router = APIRouter()
message_service = MessageService(MessageRepository(), BookingRepository(), TripRepository())


@router.get("/{booking_id}", response_model=list[MessageResponse])
def list_messages(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return message_service.list_messages(db, current_user, booking_id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{booking_id}", response_model=MessageResponse)
def send_message(
    booking_id: UUID,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        message = message_service.send_message(db, current_user, booking_id, payload.content)
        db.commit()
        return message
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
