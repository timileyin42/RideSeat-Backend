"""Notification routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.constants import NotificationType
from app.core.dependencies import get_current_user, get_db, rate_limit
from app.repositories.device_repo import DeviceRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.user_repo import UserRepository
from app.schemas.device import DeviceRegistrationRequest, DeviceResponse
from app.schemas.base import DataResponse
from app.schemas.notification import NotificationResponse, SendNotificationRequest
from app.services.notification_service import NotificationService

router = APIRouter()
notification_service = NotificationService(DeviceRepository(), NotificationRepository(), UserRepository())


@router.post("/devices/register", response_model=DataResponse[DeviceResponse], status_code=201)
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
        return DataResponse(data=DeviceResponse.model_validate(device))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected error in register_device")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=DataResponse[list[NotificationResponse]])
def list_notifications(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return DataResponse(data=notification_service.list_notifications(db, current_user, limit=limit, offset=offset))


@router.post("/send", response_model=DataResponse[dict])
def send_notification(
    payload: SendNotificationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    notification_service.create_notification(
        db,
        payload.recipient_id,
        NotificationType.GENERAL,
        payload.title,
        payload.body,
    )
    db.commit()
    return DataResponse(data={"message": "Notification sent"})


@router.post("/{notification_id}/read", response_model=DataResponse[NotificationResponse])
def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        notification = notification_service.mark_read(db, current_user, notification_id)
        db.commit()
        return DataResponse(data=notification)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
