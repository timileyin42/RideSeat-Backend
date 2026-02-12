"""Booking routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.constants import BookingStatus
from app.core.dependencies import get_current_user, get_db, rate_limit
from app.repositories.booking_repo import BookingRepository
from app.repositories.device_repo import DeviceRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.schemas.booking import BookingCreate, BookingResponse, BookingStatusUpdate
from app.services.booking_service import BookingService
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.services.payment_service import PaymentService

router = APIRouter()
payment_service = PaymentService(PaymentRepository(), BookingRepository(), TripRepository(), UserRepository())
notification_service = NotificationService(DeviceRepository(), NotificationRepository(), UserRepository())
booking_service = BookingService(
    BookingRepository(),
    TripRepository(),
    UserRepository(),
    EmailService(),
    notification_service,
    payment_service,
)


@router.post("", response_model=BookingResponse)
def create_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("bookings_create", limit=10, window_seconds=60)),
):
    try:
        booking = booking_service.create_booking(db, current_user, UUID(payload.trip_id), payload.seats)
        db.commit()
        return booking
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/me", response_model=list[BookingResponse])
def list_my_bookings(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return booking_service.list_bookings(db, current_user)


@router.get("/driver", response_model=list[BookingResponse])
def list_driver_bookings(
    status: BookingStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return booking_service.list_bookings_for_driver(db, current_user, status=status)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.patch("/{booking_id}/status", response_model=BookingResponse)
def update_booking_status(
    booking_id: UUID,
    payload: BookingStatusUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("bookings_status", limit=10, window_seconds=60)),
):
    try:
        booking = booking_service.update_status(db, current_user, booking_id, payload.status)
        db.commit()
        return booking
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("bookings_cancel", limit=10, window_seconds=60)),
):
    try:
        booking = booking_service.cancel_booking(db, current_user, booking_id)
        db.commit()
        return booking
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
