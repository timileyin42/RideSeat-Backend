"""Admin routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db
from app.repositories.booking_repo import BookingRepository
from app.repositories.device_repo import DeviceRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.schemas.admin import AdminMetricsResponse, VerificationRejectRequest
from app.schemas.base import DataResponse
from app.schemas.booking import BookingDisputeResolve, BookingResponse
from app.schemas.payment import PaymentResponse
from app.schemas.trip import TripResponse
from app.schemas.user import UserPrivateResponse
from app.services.booking_service import BookingService
from app.services.admin_service import AdminService
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.services.payment_service import PaymentService
from app.services.trip_service import TripService
from app.services.user_service import UserService

router = APIRouter()
user_repo = UserRepository()
payment_repo = PaymentRepository()
booking_repo = BookingRepository()
user_service = UserService(UserRepository(), BookingRepository())
trip_service = TripService(TripRepository())
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
admin_service = AdminService(
    UserRepository(),
    TripRepository(),
    BookingRepository(),
    PaymentRepository(),
)


@router.get("/users", response_model=DataResponse[list[UserPrivateResponse]])
def list_users(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, description="Search by name or email"),
    role: str | None = Query(default=None, description="Filter by role: DRIVER, PASSENGER, BOTH"),
    verification_status: str | None = Query(default=None, description="Filter by identity_verification_status: PENDING, APPROVED, REJECTED"),
):
    try:
        return DataResponse(data=user_service.list_users(
            db, current_user,
            limit=limit, offset=offset,
            search=search, role=role, verification_status=verification_status,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/users/pending-verification", response_model=DataResponse[list[UserPrivateResponse]])
def list_pending_verifications(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    users = user_repo.list_pending_verifications(db, limit=limit, offset=offset)
    return DataResponse(data=users)


@router.get("/metrics", response_model=DataResponse[AdminMetricsResponse])
def get_metrics(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    period: str = Query(default="all", description="Date range: today | 7d | 30d | all"),
):
    try:
        return DataResponse(data=admin_service.get_metrics(db, current_user, period=period))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/metrics/bookings-timeseries")
def bookings_timeseries(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    data = booking_repo.bookings_timeseries(db, days=days)
    return DataResponse(data=data)


@router.get("/metrics/revenue-timeseries")
def revenue_timeseries(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    data = payment_repo.revenue_timeseries(db, days=days)
    return DataResponse(data=data)


@router.get("/activity")
def activity_feed(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    from app.models.user import User
    from app.models.booking import Booking
    from app.models.payment import Payment
    from app.core.constants import BookingStatus, PaymentStatus, IdentityVerificationStatus
    from sqlalchemy import select
    from app.utils.datetime import now_utc

    events = []

    users = db.execute(select(User).order_by(User.created_at.desc()).limit(limit)).scalars().all()
    for u in users:
        events.append({
            "type": "signup",
            "message": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
            "detail": f"New user registered ({u.email})",
            "timestamp": u.created_at.isoformat(),
        })
        if u.identity_verification_status == IdentityVerificationStatus.PENDING and u.updated_at != u.created_at:
            events.append({
                "type": "verification_pending",
                "message": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
                "detail": "Submitted identity for verification",
                "timestamp": u.updated_at.isoformat(),
            })

    bookings = db.execute(select(Booking).order_by(Booking.created_at.desc()).limit(limit)).scalars().all()
    for b in bookings:
        events.append({
            "type": "booking",
            "message": f"Booking {str(b.id)[:8]}",
            "detail": f"Booking {b.status.lower()} — £{float(b.total_amount):.2f}",
            "timestamp": b.created_at.isoformat(),
        })

    payments = db.execute(
        select(Payment).where(Payment.status == PaymentStatus.SUCCEEDED).order_by(Payment.created_at.desc()).limit(limit)
    ).scalars().all()
    for p in payments:
        events.append({
            "type": "payment",
            "message": f"Payment £{float(p.amount):.2f}",
            "detail": f"Payment succeeded for booking {str(p.booking_id)[:8]}",
            "timestamp": p.created_at.isoformat(),
        })

    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return DataResponse(data=events[:limit])


@router.get("/payments", response_model=DataResponse[list[PaymentResponse]])
def list_payments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None, description="Filter by status: SUCCEEDED, FAILED, REFUNDED"),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    payments = payment_repo.list_all(db, limit=limit, offset=offset, status=status)
    return DataResponse(data=payments)


@router.get("/trips", response_model=DataResponse[list[TripResponse]])
def list_trips(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        return DataResponse(data=trip_service.list_all_trips(db, current_user, limit=limit, offset=offset))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/bookings", response_model=DataResponse[list[BookingResponse]])
def list_bookings(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        return DataResponse(data=booking_service.list_all_bookings(db, current_user, limit=limit, offset=offset))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/bookings/{booking_id}/resolve", response_model=DataResponse[BookingResponse])
def resolve_booking_dispute(
    booking_id: UUID,
    payload: BookingDisputeResolve,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        booking = booking_service.resolve_dispute(db, current_user, booking_id, payload.status)
        db.commit()
        return DataResponse(data=booking)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/users/{user_id}/verification/approve", response_model=DataResponse[UserPrivateResponse])
def approve_identity(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        user = user_service.approve_identity(db, current_user, user_id, email_service=EmailService())
        db.commit()
        return DataResponse(data=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/users/{user_id}/verification/reject", response_model=DataResponse[UserPrivateResponse])
def reject_identity(
    user_id: UUID,
    payload: VerificationRejectRequest | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        reason = payload.reason if payload else None
        user = user_service.reject_identity(db, current_user, user_id, reason=reason, email_service=EmailService())
        db.commit()
        return DataResponse(data=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/users/{user_id}/verify-email", response_model=DataResponse[UserPrivateResponse])
def admin_verify_email(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Force-verify a user's email address (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    user = UserRepository().get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_email_verified = True
    UserRepository().update(db, user)
    db.commit()
    return DataResponse(data=user)
