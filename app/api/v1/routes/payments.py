"""Payment routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db, rate_limit
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.schemas.payment import PaymentIntentCreate, PaymentResponse
from app.services.payment_service import PaymentService

router = APIRouter()
payment_service = PaymentService(PaymentRepository(), BookingRepository(), TripRepository(), UserRepository())


@router.post("/intent", response_model=PaymentResponse)
def create_payment_intent(
    payload: PaymentIntentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("payments_intent", limit=5, window_seconds=60)),
):
    try:
        payment = payment_service.create_intent_background(
            db,
            UUID(payload.booking_id),
            current_user.id,
            background_tasks,
        )
        db.commit()
        return payment
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/webhook", response_model=PaymentResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default=""),
    db: Session = Depends(get_db),
):
    try:
        payload = await request.body()
        payment = payment_service.handle_webhook(db, payload, stripe_signature)
        db.commit()
        return payment
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{booking_id}", response_model=PaymentResponse)
def get_payment_status(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return payment_service.get_payment_status_for_user(db, booking_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
