"""Payment routes."""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db, rate_limit
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.schemas.base import DataResponse
from app.schemas.payment import (
    ConnectOnboardResponse,
    ConnectStatusResponse,
    PaymentIntentCreate,
    PaymentResponse,
)
from app.services.payment_service import PaymentService

router = APIRouter()
payment_service = PaymentService(PaymentRepository(), BookingRepository(), TripRepository(), UserRepository())


@router.post("/intent", response_model=DataResponse[PaymentResponse])
def create_payment_intent(
    payload: PaymentIntentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("payments_intent", limit=5, window_seconds=60)),
):
    try:
        payment = payment_service.create_payment_intent(db, UUID(payload.booking_id), current_user.id)
        db.commit()
        return DataResponse(data=payment)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    try:
        payload = await request.body()
        payment_service.handle_webhook(db, payload, stripe_signature)
        db.commit()
        return {"received": True}
    except ValueError as exc:
        db.rollback()
        # Return 200 for unhandled event types so Stripe doesn't retry them
        detail = str(exc)
        if "Unhandled event type" in detail:
            return {"received": True}
        raise HTTPException(status_code=400, detail=detail) from exc


@router.get("/history", response_model=DataResponse[list[PaymentResponse]])
def list_payment_history(
    period: str = Query(pattern="^(7d|30d|6m|1y)$"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("payments_history", limit=20, window_seconds=60)),
):
    try:
        return DataResponse(data=payment_service.list_payment_history(db, current_user.id, period))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class ConnectOnboardRequest(BaseModel):
    return_url: str
    refresh_url: str


@router.post("/connect/onboard", response_model=DataResponse[ConnectOnboardResponse])
def connect_onboard(
    payload: ConnectOnboardRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create or resume Stripe Express onboarding for the driver. Returns a one-time URL."""
    try:
        result = payment_service.create_connect_account(
            db, current_user.id, payload.return_url, payload.refresh_url
        )
        db.commit()
        return DataResponse(data=result)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/connect/status", response_model=DataResponse[ConnectStatusResponse])
def connect_status(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Check whether the driver's Stripe Connect account is fully onboarded."""
    try:
        return DataResponse(data=payment_service.get_connect_status(db, current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{booking_id}", response_model=DataResponse[PaymentResponse])
def get_payment_status(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return DataResponse(data=payment_service.get_payment_status_for_user(db, booking_id, current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
