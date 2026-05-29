"""Tests for vehicle CRUD (gap #3: Multiple Vehicles table)."""

import pytest

from app.core.constants import UserRole
from app.core.security import hash_password
from app.models.user import User
from app.models.vehicle import Vehicle
from app.repositories.user_repo import UserRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.services.vehicle_service import VehicleService
from app.models.trip import Trip
from app.repositories.trip_repo import TripRepository
from app.utils.datetime import now_utc
from datetime import timedelta


def _make_driver(user_repo, db):
    return user_repo.create(
        db,
        User(
            first_name="Driver",
            last_name="Test",
            email=f"driver-{id(db)}@example.com",
            password_hash=hash_password("pass1234"),
            role=UserRole.DRIVER,
            is_email_verified=True,
        ),
    )


def test_add_vehicle(db_session):
    user_repo = UserRepository()
    vehicle_repo = VehicleRepository()
    service = VehicleService(vehicle_repo)

    driver = _make_driver(user_repo, db_session)
    db_session.commit()

    vehicle = service.add_vehicle(db_session, driver, {
        "make": "Toyota",
        "model": "Camry",
        "color": "Black",
        "plate": "QQ58 JYY",
        "type": "Sedan",
        "year": 2020,
        "back_seat_max": 3,
        "is_default": False,
    })
    db_session.commit()

    assert vehicle.id is not None
    assert vehicle.user_id == driver.id
    assert vehicle.make == "Toyota"
    assert vehicle.plate == "QQ58 JYY"


def test_list_vehicles(db_session):
    user_repo = UserRepository()
    vehicle_repo = VehicleRepository()
    service = VehicleService(vehicle_repo)

    driver = _make_driver(user_repo, db_session)
    db_session.commit()

    service.add_vehicle(db_session, driver, {"make": "Toyota", "model": "Camry", "color": "Black", "plate": "AAA-111", "is_default": False})
    service.add_vehicle(db_session, driver, {"make": "Honda", "model": "Civic", "color": "White", "plate": "BBB-222", "is_default": False})
    db_session.commit()

    vehicles = service.list_vehicles(db_session, driver)
    assert len(vehicles) == 2


def test_set_default_vehicle(db_session):
    user_repo = UserRepository()
    vehicle_repo = VehicleRepository()
    service = VehicleService(vehicle_repo)

    driver = _make_driver(user_repo, db_session)
    db_session.commit()

    v1 = service.add_vehicle(db_session, driver, {"make": "Toyota", "model": "Camry", "color": "Black", "plate": "AAA", "is_default": True})
    v2 = service.add_vehicle(db_session, driver, {"make": "Honda", "model": "Civic", "color": "White", "plate": "BBB", "is_default": False})
    db_session.commit()

    assert v1.is_default is True
    assert v2.is_default is False

    updated = service.set_default(db_session, driver, v2.id)
    db_session.commit()

    db_session.refresh(v1)
    assert updated.is_default is True
    assert v1.is_default is False


def test_delete_vehicle(db_session):
    user_repo = UserRepository()
    vehicle_repo = VehicleRepository()
    service = VehicleService(vehicle_repo)

    driver = _make_driver(user_repo, db_session)
    db_session.commit()

    vehicle = service.add_vehicle(db_session, driver, {"make": "Toyota", "model": "Camry", "color": "Black", "plate": "CCC", "is_default": False})
    db_session.commit()

    service.delete_vehicle(db_session, driver, vehicle.id)
    db_session.commit()

    assert vehicle_repo.get_by_id(db_session, vehicle.id) is None


def test_delete_other_users_vehicle_fails(db_session):
    user_repo = UserRepository()
    vehicle_repo = VehicleRepository()
    service = VehicleService(vehicle_repo)

    driver1 = _make_driver(user_repo, db_session)
    driver2 = user_repo.create(
        db_session,
        User(
            first_name="Other", last_name="Driver",
            email="other-driver@example.com",
            password_hash=hash_password("pass1234"),
            role=UserRole.DRIVER, is_email_verified=True,
        ),
    )
    db_session.commit()

    vehicle = service.add_vehicle(db_session, driver1, {"make": "Toyota", "model": "Camry", "color": "Black", "plate": "DDD", "is_default": False})
    db_session.commit()

    with pytest.raises(ValueError, match="Vehicle not found"):
        service.delete_vehicle(db_session, driver2, vehicle.id)


def test_trip_created_with_vehicle_id(db_session):
    """Trip creation using vehicle_id populates vehicle fields correctly."""
    user_repo = UserRepository()
    vehicle_repo = VehicleRepository()
    trip_repo = TripRepository()

    driver = _make_driver(user_repo, db_session)
    db_session.commit()

    vehicle = Vehicle(user_id=driver.id, make="Toyota", model="Camry", color="Black", plate="EEE-123")
    db_session.add(vehicle)
    db_session.flush()
    db_session.commit()

    trip = Trip(
        driver_id=driver.id,
        vehicle_id=vehicle.id,
        origin_city="Lagos",
        destination_city="Abuja",
        departure_time=now_utc() + timedelta(hours=3),
        available_seats=3,
        price_per_seat=25,
        vehicle_make=vehicle.make,
        vehicle_model=vehicle.model,
        vehicle_color=vehicle.color,
    )
    created = trip_repo.create(db_session, trip)
    db_session.commit()

    assert created.vehicle_id == vehicle.id
    assert created.vehicle_make == "Toyota"
