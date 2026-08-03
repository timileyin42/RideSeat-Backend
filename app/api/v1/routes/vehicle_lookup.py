"""Vehicle lookup routes — makes, models, years for dropdown autocomplete."""

import json
import logging
import urllib.request
from datetime import datetime
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query

from app.schemas.base import DataResponse

logger = logging.getLogger(__name__)
router = APIRouter()

_VEHICLESDB = "https://raw.githubusercontent.com/vehiclesdb/vehiclesdb/main/catalog"
_VALID_TYPES = {"car", "van", "motorcycle", "moped", "truck", "bus"}

# Fallback makes shown if CDN is unreachable
_FALLBACK_MAKES = [
    "Abarth", "Alfa Romeo", "Aston Martin", "Audi", "Bentley", "BMW", "Bugatti",
    "Chevrolet", "Chrysler", "Citroën", "Cupra", "Dacia", "DS", "Ferrari", "Fiat",
    "Ford", "Honda", "Hyundai", "Infiniti", "Jaguar", "Jeep", "Kia", "Lamborghini",
    "Land Rover", "Lexus", "Maserati", "Mazda", "McLaren", "Mercedes-Benz", "MG",
    "MINI", "Mitsubishi", "Nissan", "Peugeot", "Porsche", "Renault", "Rolls-Royce",
    "SEAT", "Skoda", "Smart", "Subaru", "Suzuki", "Tesla", "Toyota", "Vauxhall",
    "Volkswagen", "Volvo",
]


@lru_cache(maxsize=6)
def _fetch_makes(kind: str) -> list[dict]:
    """Fetch and cache makes from vehiclesdb CDN. Cached per process."""
    url = f"{_VEHICLESDB}/{kind}/makes.json"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        logger.warning("vehiclesdb makes fetch failed, using fallback", exc_info=exc)
        return [{"id": m.lower().replace(" ", "-"), "name": m} for m in _FALLBACK_MAKES]


@lru_cache(maxsize=6)
def _fetch_models(kind: str) -> list[dict]:
    """Fetch and cache all models for a kind. Cached per process."""
    url = f"{_VEHICLESDB}/{kind}/models.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        logger.warning("vehiclesdb models fetch failed", exc_info=exc)
        return []


@router.get("/makes", response_model=DataResponse[list[dict]])
def list_makes(
    type: str = Query(default="car", description="Vehicle type: car | van | motorcycle | moped | truck | bus"),
):
    """Return all makes for a vehicle type, sorted alphabetically."""
    kind = type.lower()
    if kind not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {', '.join(sorted(_VALID_TYPES))}")
    raw = _fetch_makes(kind)
    makes = sorted(
        [{"id": m["id"], "name": m["name"]} for m in raw],
        key=lambda x: x["name"].lower(),
    )
    return DataResponse(data=makes)


@router.get("/models", response_model=DataResponse[list[dict]])
def list_models(
    make: str = Query(..., description="Make ID (slug), e.g. volkswagen"),
    type: str = Query(default="car", description="Vehicle type: car | van | motorcycle"),
):
    """Return all models for a given make, sorted alphabetically."""
    kind = type.lower()
    if kind not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {', '.join(sorted(_VALID_TYPES))}")
    raw = _fetch_models(kind)
    models = sorted(
        [{"id": m["id"], "name": m["name"]} for m in raw if m.get("make_id") == make.lower()],
        key=lambda x: x["name"].lower(),
    )
    return DataResponse(data=models)


@router.get("/years", response_model=DataResponse[list[int]])
def list_years():
    """Return vehicle years from current year down to 1990."""
    current = datetime.utcnow().year
    return DataResponse(data=list(range(current, 1989, -1)))
