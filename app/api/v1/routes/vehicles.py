"""Vehicle routes (under /users/me/vehicles)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.base import DataResponse
from app.schemas.vehicle import VehicleCreate, VehicleResponse, VehicleUpdate
from app.services.vehicle_service import VehicleService

router = APIRouter()
vehicle_service = VehicleService(VehicleRepository())


@router.post("", response_model=DataResponse[VehicleResponse], status_code=201)
def add_vehicle(
    payload: VehicleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        vehicle = vehicle_service.add_vehicle(db, current_user, payload.model_dump())
        db.commit()
        return DataResponse(data=vehicle)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=DataResponse[list[VehicleResponse]])
def list_vehicles(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return DataResponse(data=vehicle_service.list_vehicles(db, current_user))


@router.put("/{vehicle_id}", response_model=DataResponse[VehicleResponse])
def update_vehicle(
    vehicle_id: UUID,
    payload: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        vehicle = vehicle_service.update_vehicle(db, current_user, vehicle_id, payload.model_dump())
        db.commit()
        return DataResponse(data=vehicle)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        vehicle_service.delete_vehicle(db, current_user, vehicle_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{vehicle_id}/default", response_model=DataResponse[VehicleResponse])
def set_default_vehicle(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        vehicle = vehicle_service.set_default(db, current_user, vehicle_id)
        db.commit()
        return DataResponse(data=vehicle)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
