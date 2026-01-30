"""Admin routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.schemas.admin import AdminMetricsResponse
from app.schemas.booking import BookingDisputeResolve, BookingResponse
from app.schemas.trip import TripResponse
from app.schemas.user import UserPrivateResponse
from app.services.booking_service import BookingService
from app.services.admin_service import AdminService
from app.services.email_service import EmailService
from app.services.payment_service import PaymentService
from app.services.trip_service import TripService
from app.services.user_service import UserService

router = APIRouter()
user_service = UserService(UserRepository())
trip_service = TripService(TripRepository())
payment_service = PaymentService(PaymentRepository(), BookingRepository(), TripRepository(), UserRepository())
booking_service = BookingService(
    BookingRepository(),
    TripRepository(),
    UserRepository(),
    EmailService(),
    payment_service,
)
admin_service = AdminService(
    UserRepository(),
    TripRepository(),
    BookingRepository(),
    PaymentRepository(),
)


@router.get("/users", response_model=list[UserPrivateResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        return user_service.list_users(db, current_user, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/metrics", response_model=AdminMetricsResponse)
def get_metrics(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return admin_service.get_metrics(db, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/trips", response_model=list[TripResponse])
def list_trips(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        return trip_service.list_all_trips(db, current_user, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/bookings", response_model=list[BookingResponse])
def list_bookings(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        return booking_service.list_all_bookings(db, current_user, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/bookings/{booking_id}/resolve", response_model=BookingResponse)
def resolve_booking_dispute(
    booking_id: UUID,
    payload: BookingDisputeResolve,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        booking = booking_service.resolve_dispute(db, current_user, booking_id, payload.status)
        db.commit()
        return booking
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
