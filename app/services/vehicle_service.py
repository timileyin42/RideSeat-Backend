"""Vehicle service."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.vehicle import Vehicle
from app.repositories.vehicle_repo import VehicleRepository


class VehicleService:
    def __init__(self, vehicle_repo: VehicleRepository) -> None:
        self.vehicle_repo = vehicle_repo

    def add_vehicle(self, db: Session, user: User, data: dict) -> Vehicle:
        if data.get("is_default"):
            self.vehicle_repo.unset_default(db, user.id)
        vehicle = Vehicle(user_id=user.id, **data)
        return self.vehicle_repo.create(db, vehicle)

    def list_vehicles(self, db: Session, user: User) -> list[Vehicle]:
        return self.vehicle_repo.list_by_user(db, user.id)

    def get_vehicle(self, db: Session, user: User, vehicle_id: UUID) -> Vehicle:
        vehicle = self.vehicle_repo.get_by_id(db, vehicle_id)
        if not vehicle or vehicle.user_id != user.id:
            raise ValueError("Vehicle not found")
        return vehicle

    def update_vehicle(self, db: Session, user: User, vehicle_id: UUID, updates: dict) -> Vehicle:
        vehicle = self.vehicle_repo.get_by_id(db, vehicle_id)
        if not vehicle or vehicle.user_id != user.id:
            raise ValueError("Vehicle not found")
        if updates.get("is_default"):
            self.vehicle_repo.unset_default(db, user.id)
        for key, value in updates.items():
            if value is not None:
                setattr(vehicle, key, value)
        return self.vehicle_repo.update(db, vehicle)

    def delete_vehicle(self, db: Session, user: User, vehicle_id: UUID) -> None:
        vehicle = self.vehicle_repo.get_by_id(db, vehicle_id)
        if not vehicle or vehicle.user_id != user.id:
            raise ValueError("Vehicle not found")
        self.vehicle_repo.delete(db, vehicle)

    def set_default(self, db: Session, user: User, vehicle_id: UUID) -> Vehicle:
        vehicle = self.vehicle_repo.get_by_id(db, vehicle_id)
        if not vehicle or vehicle.user_id != user.id:
            raise ValueError("Vehicle not found")
        self.vehicle_repo.unset_default(db, user.id)
        vehicle.is_default = True
        return self.vehicle_repo.update(db, vehicle)
