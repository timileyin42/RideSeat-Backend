"""Notification service — in-app, SMS, and FCM push."""

import base64
import json
from urllib import request as http_request
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import NotificationType
from app.models.device import Device
from app.models.notification import Notification
from app.models.user import User
from app.repositories.device_repo import DeviceRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.user_repo import UserRepository
from app.utils.datetime import now_utc

# Firebase Admin app is initialised once and reused for all requests
_firebase_app = None


def _get_firebase_app(credentials_json: str):
    import firebase_admin
    from firebase_admin import credentials as fb_creds

    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app
    raw = base64.b64decode(credentials_json).decode("utf-8")
    info = json.loads(raw)
    cred = fb_creds.Certificate(info)
    _firebase_app = firebase_admin.initialize_app(cred, name="Rideway")
    return _firebase_app


class NotificationService:
    def __init__(
        self,
        device_repo: DeviceRepository,
        notification_repo: NotificationRepository,
        user_repo: UserRepository,
    ) -> None:
        self.device_repo = device_repo
        self.notification_repo = notification_repo
        self.user_repo = user_repo
        self.settings = get_settings()

    # ── device registration ────────────────────────────────────────────────────

    def register_device(
        self,
        db: Session,
        user: User,
        device_token: str,
        platform,
        device_name: str | None,
        app_version: str | None,
    ) -> Device:
        existing = self.device_repo.get_by_token(db, device_token)
        if existing:
            existing.user_id = user.id
            existing.platform = platform
            existing.device_name = device_name
            existing.app_version = app_version
            existing.last_seen_at = now_utc()
            return self.device_repo.update(db, existing)
        device = Device(
            user_id=user.id,
            device_token=device_token,
            platform=platform,
            device_name=device_name,
            app_version=app_version,
            last_seen_at=now_utc(),
        )
        return self.device_repo.create(db, device)

    def update_device_token(
        self,
        db: Session,
        user: User,
        old_device_token: str,
        new_device_token: str,
        platform,
        device_name: str | None,
        app_version: str | None,
    ) -> Device:
        existing = self.device_repo.get_by_token(db, old_device_token)
        if existing:
            existing.user_id = user.id
            existing.device_token = new_device_token
            if platform is not None:
                existing.platform = platform
            if device_name is not None:
                existing.device_name = device_name
            if app_version is not None:
                existing.app_version = app_version
            existing.last_seen_at = now_utc()
            return self.device_repo.update(db, existing)
        return self.register_device(db, user, new_device_token, platform, device_name, app_version)

    # ── in-app notifications ───────────────────────────────────────────────────

    def list_notifications(self, db: Session, user: User, limit: int, offset: int) -> list[Notification]:
        return self.notification_repo.list_by_user(db, user.id, limit=limit, offset=offset)

    def mark_read(self, db: Session, user: User, notification_id: UUID) -> Notification:
        notification = self.notification_repo.get_by_id(db, notification_id)
        if not notification or notification.user_id != user.id:
            raise ValueError("Notification not found")
        if not notification.is_read:
            notification.is_read = True
            notification = self.notification_repo.update(db, notification)
        return notification

    def create_notification(
        self,
        db: Session,
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        body: str,
    ) -> Notification | None:
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            return None

        # 1. In-app notification (stored in DB)
        notification = None
        if user.notify_in_app:
            notification = Notification(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                body=body,
            )
            notification = self.notification_repo.create(db, notification)

        # 2. FCM push notification
        if user.notify_push:
            devices = self.device_repo.list_by_user(db, user_id)
            stale_tokens: list[Device] = []
            for device in devices:
                sent = self._send_push(device.device_token, title, body, notification_type)
                if not sent:
                    stale_tokens.append(device)
            for device in stale_tokens:
                self.device_repo.delete(db, device)

        # 3. SMS for booking-related events
        if (
            user.notify_sms
            and user.phone_number
            and user.is_phone_verified
            and notification_type in {NotificationType.BOOKING_REQUEST, NotificationType.BOOKING_CANCELLED}
        ):
            self._send_sms(user.phone_number, title, body)

        return notification

    # ── FCM push ───────────────────────────────────────────────────────────────

    def _send_push(
        self,
        device_token: str,
        title: str,
        body: str,
        notification_type: NotificationType,
    ) -> bool:
        """Send an FCM push notification. Returns False if the token is invalid/expired."""
        creds_json = self.settings.gcp_credentials_json
        if not creds_json:
            return True  # No FCM config — silently skip, don't mark token as stale

        try:
            from firebase_admin import messaging

            app = _get_firebase_app(creds_json)

            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={"type": notification_type.value},
                token=device_token,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        sound="default",
                        channel_id="rideway_notifications",
                        click_action="FLUTTER_NOTIFICATION_CLICK",
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound="default", badge=1),
                    ),
                ),
            )
            messaging.send(message, app=app)
            return True

        except Exception as exc:
            from firebase_admin import messaging as fb_msg
            # Token no longer registered on FCM — safe to remove from DB
            if isinstance(exc, fb_msg.UnregisteredError):
                return False
            # Any other error (network, config) — don't delete the token
            return True

    # ── SMS (Termii) ───────────────────────────────────────────────────────────

    def _send_sms(self, phone_number: str, title: str, body: str) -> None:
        if not self.settings.termii_api_key or not self.settings.termii_sender_id:
            return
        base_url = self.settings.termii_base_url.rstrip("/")
        payload = {
            "to": phone_number,
            "from": self.settings.termii_sender_id,
            "sms": f"{title}: {body}",
            "type": "plain",
            "channel": "generic",
            "api_key": self.settings.termii_api_key,
        }
        data = json.dumps(payload).encode("utf-8")
        req = http_request.Request(
            f"{base_url}/api/sms/send",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with http_request.urlopen(req, timeout=10):
                return None
        except Exception:
            return None
