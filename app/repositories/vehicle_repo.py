"""Vehicle repository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vehicle import Vehicle


class VehicleRepository:
    def get_by_id(self, db: Session, vehicle_id: UUID) -> Vehicle | None:
        return db.get(Vehicle, vehicle_id)

    def create(self, db: Session, vehicle: Vehicle) -> Vehicle:
        db.add(vehicle)
        db.flush()
        return vehicle

    def update(self, db: Session, vehicle: Vehicle) -> Vehicle:
        db.add(vehicle)
        db.flush()
        return vehicle

    def delete(self, db: Session, vehicle: Vehicle) -> None:
        db.delete(vehicle)
        db.flush()

    def list_by_user(self, db: Session, user_id: UUID) -> list[Vehicle]:
        stmt = (
            select(Vehicle)
            .where(Vehicle.user_id == user_id)
            .order_by(Vehicle.is_default.desc(), Vehicle.created_at)
        )
        return list(db.execute(stmt).scalars().all())

    def unset_default(self, db: Session, user_id: UUID) -> None:
        stmt = select(Vehicle).where(Vehicle.user_id == user_id, Vehicle.is_default.is_(True))
        for vehicle in db.execute(stmt).scalars().all():
            vehicle.is_default = False
            db.add(vehicle)
        db.flush()
