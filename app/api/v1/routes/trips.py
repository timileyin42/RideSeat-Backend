"""Trip routes."""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db
from app.repositories.trip_repo import TripRepository
from app.schemas.trip import TripCreate, TripResponse, TripUpdate
from app.services.trip_service import TripService

router = APIRouter()
trip_service = TripService(TripRepository())


@router.post("", response_model=TripResponse)
def create_trip(
    payload: TripCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        trip = trip_service.create_trip(db, current_user, payload.model_dump())
        db.commit()
        return trip
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/search", response_model=list[TripResponse])
def search_trips(
    origin_city: str | None = None,
    destination_city: str | None = None,
    departure_date: date | None = None,
    passengers: int | None = Query(default=None, ge=1, le=6),
    db: Session = Depends(get_db),
):
    return trip_service.search_trips(db, origin_city, destination_city, departure_date, passengers)


@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(trip_id: UUID, db: Session = Depends(get_db)):
    try:
        return trip_service.get_trip(db, trip_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{trip_id}", response_model=TripResponse)
def update_trip(
    trip_id: UUID,
    payload: TripUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        trip = trip_service.update_trip(db, current_user, trip_id, payload.model_dump())
        db.commit()
        return trip
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{trip_id}", response_model=TripResponse)
def cancel_trip(
    trip_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        trip = trip_service.cancel_trip(db, current_user, trip_id)
        db.commit()
        return trip
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
