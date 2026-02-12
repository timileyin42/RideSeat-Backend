"""Device repository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device


class DeviceRepository:
    def get_by_token(self, db: Session, token: str) -> Device | None:
        stmt = select(Device).where(Device.device_token == token)
        return db.execute(stmt).scalar_one_or_none()

    def list_by_user(self, db: Session, user_id: UUID) -> list[Device]:
        stmt = select(Device).where(Device.user_id == user_id)
        return list(db.execute(stmt).scalars().all())

    def create(self, db: Session, device: Device) -> Device:
        db.add(device)
        db.flush()
        return device

    def update(self, db: Session, device: Device) -> Device:
        db.add(device)
        db.flush()
        return device
