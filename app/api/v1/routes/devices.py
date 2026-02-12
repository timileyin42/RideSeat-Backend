"""Device routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, rate_limit
from app.repositories.device_repo import DeviceRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.user_repo import UserRepository
from app.schemas.device import DeviceResponse, DeviceTokenUpdateRequest
from app.services.notification_service import NotificationService

router = APIRouter()
notification_service = NotificationService(DeviceRepository(), NotificationRepository(), UserRepository())


@router.post("/update-token", response_model=DeviceResponse)
def update_device_token(
    payload: DeviceTokenUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("devices_update_token", limit=20, window_seconds=60)),
):
    try:
        device = notification_service.update_device_token(
            db,
            current_user,
            payload.old_device_token,
            payload.new_device_token,
            payload.platform,
            payload.device_name,
            payload.app_version,
        )
        db.commit()
        return device
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
