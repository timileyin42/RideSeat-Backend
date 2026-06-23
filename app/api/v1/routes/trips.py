"""Trip routes."""

from datetime import date, datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db
from app.repositories.trip_repo import TripRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.base import DataResponse
from app.schemas.trip import TripCreate, TripResponse, TripUpdate
from app.services.trip_service import TripService

router = APIRouter()
trip_service = TripService(TripRepository())
vehicle_repo = VehicleRepository()


@router.post("", response_model=DataResponse[TripResponse], status_code=201)
def create_trip(
    payload: TripCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = payload.model_dump()
        if data.get("vehicle_id"):
            vehicle = vehicle_repo.get_by_id(db, data["vehicle_id"])
            if not vehicle or vehicle.user_id != current_user.id:
                raise HTTPException(status_code=404, detail="Vehicle not found")
            data["vehicle_make"] = vehicle.make
            data["vehicle_model"] = vehicle.model
            data["vehicle_color"] = vehicle.color
        trip = trip_service.create_trip(db, current_user, data)
        db.commit()
        return DataResponse(data=trip)
    except HTTPException:
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/mine", response_model=DataResponse[list[TripResponse]])
def my_trips(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return DataResponse(data=trip_service.trip_repo.list_by_driver(db, current_user.id))


@router.get("/search", response_model=DataResponse[list[TripResponse]])
def search_trips(
    origin_city: str | None = None,
    destination_city: str | None = None,
    departure_date: str | None = None,
    passengers: int | None = Query(default=None, ge=1, le=6),
    sort_by: Literal["departure_time", "price", "seats_remaining"] | None = None,
    order: Literal["asc", "desc"] | None = None,
    db: Session = Depends(get_db),
):
    parsed_date: date | None = None
    if departure_date:
        try:
            parsed_date = datetime.fromisoformat(departure_date).date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid departure_date. Use YYYY-MM-DD format.")
    return DataResponse(data=trip_service.search_trips(
        db, origin_city, destination_city, parsed_date, passengers,
        sort_by=sort_by, order=order,
    ))


@router.get("/{trip_id}", response_model=DataResponse[TripResponse])
def get_trip(trip_id: UUID, db: Session = Depends(get_db)):
    try:
        return DataResponse(data=trip_service.get_trip(db, trip_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{trip_id}", response_model=DataResponse[TripResponse])
def update_trip(
    trip_id: UUID,
    payload: TripUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = payload.model_dump()
        if data.get("vehicle_id"):
            vehicle = vehicle_repo.get_by_id(db, data["vehicle_id"])
            if not vehicle or vehicle.user_id != current_user.id:
                raise HTTPException(status_code=404, detail="Vehicle not found")
            data["vehicle_make"] = vehicle.make
            data["vehicle_model"] = vehicle.model
            data["vehicle_color"] = vehicle.color
        trip = trip_service.update_trip(db, current_user, trip_id, data)
        db.commit()
        return DataResponse(data=trip)
    except HTTPException:
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{trip_id}", response_model=DataResponse[TripResponse])
def cancel_trip(
    trip_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        trip = trip_service.cancel_trip(db, current_user, trip_id)
        db.commit()
        return DataResponse(data=trip)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
