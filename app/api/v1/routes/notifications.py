"""Notification routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db, rate_limit
from app.repositories.device_repo import DeviceRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.user_repo import UserRepository
from app.schemas.device import DeviceRegistrationRequest, DeviceResponse
from app.schemas.notification import NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter()
notification_service = NotificationService(DeviceRepository(), NotificationRepository(), UserRepository())


@router.post("/devices/register", response_model=DeviceResponse)
def register_device(
    payload: DeviceRegistrationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("notifications_device_register", limit=20, window_seconds=60)),
):
    try:
        device = notification_service.register_device(
            db,
            current_user,
            payload.device_token,
            payload.platform,
            payload.device_name,
            payload.app_version,
        )
        db.commit()
        return device
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return notification_service.list_notifications(db, current_user, limit=limit, offset=offset)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        notification = notification_service.mark_read(db, current_user, notification_id)
        db.commit()
        return notification
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
