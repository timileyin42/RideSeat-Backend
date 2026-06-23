"""
Smoke tests — every registered endpoint is exercised at least once.

External services are stubbed so no real network calls are made:
  - Resend (email)       → all send_* methods on EmailService patched to no-ops
  - Google Cloud Storage → fake URLs returned
  - Stripe               → no-op
  - Celery               → tasks queued but never executed
"""

import os
import pytest
import fakeredis
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set env vars BEFORE any app imports so get_settings() picks them up
os.environ["JWT_SECRET_KEY"] = "smoke-test-secret-key-long-enough-32chars"
os.environ["ADMIN_EMAIL"] = "admin@test.com"
os.environ["ADMIN_PASSWORD"] = "AdminPass1!"
os.environ["FRONTEND_BASE_URL"] = "https://test.rideway.app"
os.environ["RESEND_API_KEY"] = "re_test_key"
os.environ["EMAIL_FROM"] = "test@rideway.app"
os.environ["REFERRAL_BASE_URL"] = "https://test.rideway.app/r"
os.environ["SPOTIFY_PLAYLIST_URL"] = "https://open.spotify.com/test"

from app.core.config import get_settings
from app.core.database import Base
from app.core.dependencies import get_db, rate_limit_state
from app.models.user import User
from app.main import create_app
from app.services import otp_service

# Shared in-process fake Redis for all OTP operations in tests
_fake_redis = fakeredis.FakeRedis(decode_responses=True)

# ── in-memory SQLite DB ────────────────────────────────────────────────────────
_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


# ── patches applied for the whole module ──────────────────────────────────────
# Patch every EmailService send method at the class level so config checks
# and real Resend calls are both bypassed for all existing instances.
_EMAIL_METHODS = [
    "send_verification_email",
    "send_welcome_email",
    "send_password_reset_email",
    "send_trip_completed_email",
    "send_booking_request_email",
    "send_verification_submitted_email",
    "send_admin_verification_alert",
]

_email_patches = [
    patch(f"app.services.email_service.EmailService.{m}", return_value=None)
    for m in _EMAIL_METHODS
]

_other_patches = [
    # Route all OTP Redis calls to the in-process fake Redis
    patch("app.services.otp_service._client", return_value=_fake_redis),
    patch(
        "app.services.storage_service.StorageService.upload_bytes",
        return_value="https://storage.googleapis.com/bucket/fake-object",
    ),
    patch(
        "app.services.storage_service.StorageService.signed_url",
        return_value="https://storage.googleapis.com/bucket/fake-object?signed=1",
    ),
    patch("app.core.celery_app.celery_app.send_task", return_value=MagicMock()),
    patch("stripe.PaymentIntent.create", return_value=MagicMock(id="pi_stub")),
    patch("stripe.Transfer.create", return_value=MagicMock(id="tr_stub")),
    patch("app.api.admin_web.SessionLocal", _Session),
    patch("app.main.SessionLocal", _Session),
]


@pytest.fixture(scope="module")
def client():
    # Force fresh settings so env vars set above are used
    get_settings.cache_clear()

    all_patches = _email_patches + _other_patches
    started = [p.start() for p in all_patches]
    try:
        app = create_app()
        app.dependency_overrides[get_db] = _override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        for p in all_patches:
            p.stop()


@pytest.fixture(autouse=True)
def reset_db():
    rate_limit_state.clear()
    _fake_redis.flushall()  # wipe OTP keys between tests
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)


# ── helpers ────────────────────────────────────────────────────────────────────
def _register(client, email="user@test.com", password="Pass1234!", first=None, last=None):
    """Register and auto-verify so the user can log in immediately."""
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": password,
    })
    assert r.status_code == 201, r.text
    data = r.json()
    otp = _get_otp(email)
    if otp:
        client.post("/api/v1/auth/verify-email", json={"email": email, "token": otp})
    return data


def _login(client, email="user@test.com", password="Pass1234!"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _future_dt(hours=48):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _get_otp(email):
    """Read the verification OTP from fake Redis (email sending is bypassed in tests)."""
    return otp_service.get_verify_otp(email)


def _make_admin():
    from app.core.security import hash_password
    db = _Session()
    try:
        existing = db.execute(select(User).where(User.email == "admin@test.com")).scalar_one_or_none()
        if not existing:
            admin = User(
                first_name="Admin", last_name="User",
                email="admin@test.com",
                password_hash=hash_password("AdminPass1!"),
                is_admin=True, is_email_verified=True,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# 1. ROOT / HEALTH
# ══════════════════════════════════════════════════════════════════════════════

class TestRoot:
    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert b"Rideway" in r.content
        assert b"Cost-Sharing" in r.content

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ══════════════════════════════════════════════════════════════════════════════
# 2. AUTH
# ══════════════════════════════════════════════════════════════════════════════

class TestAuth:
    def test_register(self, client):
        r = client.post("/api/v1/auth/register", json={
            "email": "new@test.com", "password": "Pass1234!",
        })
        assert r.status_code == 201
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "new@test.com"
        assert data["user"]["is_email_verified"] is False

    def test_register_duplicate_email(self, client):
        _register(client)
        r = client.post("/api/v1/auth/register", json={
            "email": "user@test.com", "password": "Pass1234!",
        })
        assert r.status_code == 400

    def test_login(self, client):
        _register(client)  # auto-verifies email
        r = client.post("/api/v1/auth/login", json={
            "email": "user@test.com", "password": "Pass1234!",
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_wrong_password(self, client):
        _register(client)  # auto-verifies email
        r = client.post("/api/v1/auth/login", json={
            "email": "user@test.com", "password": "wrong",
        })
        assert r.status_code == 401

    def test_login_unverified_fails(self, client):
        client.post("/api/v1/auth/register", json={
            "email": "noverify@test.com", "password": "Pass1234!",
        })
        r = client.post("/api/v1/auth/login", json={
            "email": "noverify@test.com", "password": "Pass1234!",
        })
        assert r.status_code == 401

    def test_verify_email(self, client):
        """Register without auto-verify, fetch OTP from fake Redis, verify with email+token."""
        r = client.post("/api/v1/auth/register", json={
            "email": "unverified@test.com", "password": "Pass1234!",
        })
        assert r.status_code == 201
        otp = otp_service.get_verify_otp("unverified@test.com")
        assert otp is not None, "OTP should be stored in Redis after registration"
        r2 = client.post("/api/v1/auth/verify-email",
                         json={"email": "unverified@test.com", "token": otp})
        assert r2.status_code == 200
        assert "access_token" in r2.json()

    def test_forgot_password(self, client):
        _register(client)
        r = client.post("/api/v1/auth/forgot-password", json={"email": "user@test.com"})
        assert r.status_code == 200

    def test_forgot_password_unknown_email(self, client):
        r = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@test.com"})
        assert r.status_code in (200, 400)  # implementation may or may not reveal unknown email


# ══════════════════════════════════════════════════════════════════════════════
# 3. USERS
# ══════════════════════════════════════════════════════════════════════════════

class TestUsers:
    def test_get_me(self, client):
        _register(client)
        token = _login(client)
        r = client.get("/api/v1/users/me", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["email"] == "user@test.com"

    def test_get_me_unauthenticated(self, client):
        r = client.get("/api/v1/users/me")
        assert r.status_code == 401

    def test_update_me(self, client):
        _register(client)
        token = _login(client)
        r = client.put("/api/v1/users/me", json={"bio": "Hello Rideway"}, headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["bio"] == "Hello Rideway"

    def test_update_me_ignores_role_change(self, client):
        _register(client)
        token = _login(client)
        r = client.put("/api/v1/users/me", json={"role": "DRIVER"}, headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["role"] == "PASSENGER"

    def test_get_public_profile(self, client):
        data = _register(client)
        user_id = data["user"]["id"]
        token = _login(client)
        r = client.get(f"/api/v1/users/{user_id}", headers=_auth(token))
        assert r.status_code == 200

    def test_promos(self, client):
        _register(client)
        token = _login(client)
        r = client.get("/api/v1/users/promos", headers=_auth(token))
        assert r.status_code == 200
        assert "items" in r.json()

    def test_student_promo(self, client):
        _register(client)
        token = _login(client)
        r = client.get("/api/v1/users/promos/student", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["promo_type"] == "STUDENT"

    def test_phone_request_requires_phone(self, client):
        _register(client)
        token = _login(client)
        r = client.post("/api/v1/users/me/phone/request", headers=_auth(token))
        assert r.status_code == 400  # no phone set yet

    def test_phone_request_and_verify(self, client):
        _register(client)
        token = _login(client)
        client.put("/api/v1/users/me", json={"phone_number": "+447911123456"}, headers=_auth(token))
        r = client.post("/api/v1/users/me/phone/request", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["status"] == "sent"
        assert r.json()["channel"] in ("sms", "whatsapp", "voice")
        # Get the code directly from DB (Termii is bypassed in tests)
        db = _Session()
        try:
            user = db.execute(
                select(User).where(User.email == "user@test.com")
            ).scalar_one()
            code = user.phone_verification_token
        finally:
            db.close()
        r2 = client.post("/api/v1/users/me/phone/verify", json={"code": code}, headers=_auth(token))
        assert r2.status_code == 200
        assert r2.json()["is_phone_verified"] is True

    def test_referral_url(self, client):
        _register(client)
        token = _login(client)
        r = client.get("/api/v1/users/me/referral", headers=_auth(token))
        assert r.status_code == 200
        assert "url" in r.json()


# ══════════════════════════════════════════════════════════════════════════════
# 4. VEHICLES
# ══════════════════════════════════════════════════════════════════════════════

class TestVehicles:
    def _create_vehicle(self, client, token):
        r = client.post("/api/v1/users/me/vehicles", headers=_auth(token), json={
            "make": "Toyota", "model": "Corolla", "color": "White",
            "plate": "AB12CDE", "year": 2020, "back_seat_max": 3,
        })
        assert r.status_code == 201, r.text
        return r.json()

    def test_create_vehicle(self, client):
        _register(client)
        token = _login(client)
        v = self._create_vehicle(client, token)
        assert v["make"] == "Toyota"

    def test_list_vehicles(self, client):
        _register(client)
        token = _login(client)
        self._create_vehicle(client, token)
        r = client.get("/api/v1/users/me/vehicles", headers=_auth(token))
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_update_vehicle(self, client):
        _register(client)
        token = _login(client)
        v = self._create_vehicle(client, token)
        r = client.put(f"/api/v1/users/me/vehicles/{v['id']}", headers=_auth(token),
                       json={"color": "Blue"})
        assert r.status_code == 200
        assert r.json()["color"] == "Blue"

    def test_set_default_vehicle(self, client):
        _register(client)
        token = _login(client)
        v = self._create_vehicle(client, token)
        r = client.put(f"/api/v1/users/me/vehicles/{v['id']}/default", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["is_default"] is True

    def test_delete_vehicle(self, client):
        _register(client)
        token = _login(client)
        v = self._create_vehicle(client, token)
        r = client.delete(f"/api/v1/users/me/vehicles/{v['id']}", headers=_auth(token))
        assert r.status_code == 204


# ══════════════════════════════════════════════════════════════════════════════
# 5. TRIPS
# ══════════════════════════════════════════════════════════════════════════════

class TestTrips:
    def _create_trip(self, client, token):
        r = client.post("/api/v1/trips", headers=_auth(token), json={
            "origin_city": "London",
            "destination_city": "Manchester",
            "departure_time": _future_dt(48),
            "price_per_seat": 15.00,
            "available_seats": 3,
            "vehicle_make": "Toyota",
            "vehicle_model": "Corolla",
            "vehicle_color": "White",
        })
        assert r.status_code == 201, r.text
        return r.json()

    def test_create_trip(self, client):
        _register(client)
        token = _login(client)
        trip = self._create_trip(client, token)
        assert trip["origin_city"] == "London"

    def test_get_trip(self, client):
        _register(client)
        token = _login(client)
        trip = self._create_trip(client, token)
        r = client.get(f"/api/v1/trips/{trip['id']}", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["id"] == trip["id"]

    def test_search_trips(self, client):
        _register(client)
        token = _login(client)
        self._create_trip(client, token)
        r = client.get(
            "/api/v1/trips/search?origin_city=London&destination_city=Manchester",
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_search_with_sort(self, client):
        _register(client)
        token = _login(client)
        self._create_trip(client, token)
        r = client.get("/api/v1/trips/search?sort_by=price&order=asc", headers=_auth(token))
        assert r.status_code == 200

    def test_update_trip(self, client):
        _register(client)
        token = _login(client)
        trip = self._create_trip(client, token)
        r = client.put(f"/api/v1/trips/{trip['id']}", headers=_auth(token),
                       json={"price_per_seat": 20.00})
        assert r.status_code == 200
        assert float(r.json()["price_per_seat"]) == 20.00

    def test_delete_trip(self, client):
        _register(client)
        token = _login(client)
        trip = self._create_trip(client, token)
        r = client.delete(f"/api/v1/trips/{trip['id']}", headers=_auth(token))
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 6. BOOKINGS
# ══════════════════════════════════════════════════════════════════════════════

class TestBookings:
    def _setup(self, client):
        _register(client, email="driver@test.com", first="Driver", last="One")
        driver_token = _login(client, email="driver@test.com")
        trip_r = client.post("/api/v1/trips", headers=_auth(driver_token), json={
            "origin_city": "London", "destination_city": "Birmingham",
            "departure_time": _future_dt(48), "price_per_seat": 10.00,
            "available_seats": 2, "vehicle_make": "Ford",
            "vehicle_model": "Focus", "vehicle_color": "Black",
        })
        assert trip_r.status_code == 201, trip_r.text
        trip_id = trip_r.json()["id"]
        _register(client, email="passenger@test.com", first="Pass", last="Enger")
        passenger_token = _login(client, email="passenger@test.com")
        return driver_token, passenger_token, trip_id

    def test_create_booking(self, client):
        _, passenger_token, trip_id = self._setup(client)
        r = client.post("/api/v1/bookings", headers=_auth(passenger_token),
                        json={"trip_id": trip_id, "seats": 1})
        assert r.status_code == 201, r.text

    def test_list_my_bookings(self, client):
        _, passenger_token, trip_id = self._setup(client)
        client.post("/api/v1/bookings", headers=_auth(passenger_token),
                    json={"trip_id": trip_id, "seats": 1})
        r = client.get("/api/v1/bookings/me", headers=_auth(passenger_token))
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_list_driver_bookings(self, client):
        driver_token, passenger_token, trip_id = self._setup(client)
        client.post("/api/v1/bookings", headers=_auth(passenger_token),
                    json={"trip_id": trip_id, "seats": 1})
        r = client.get("/api/v1/bookings/driver", headers=_auth(driver_token))
        assert r.status_code == 200

    def test_cancel_booking(self, client):
        _, passenger_token, trip_id = self._setup(client)
        booking_r = client.post("/api/v1/bookings", headers=_auth(passenger_token),
                                json={"trip_id": trip_id, "seats": 1})
        booking_id = booking_r.json()["id"]
        r = client.post(f"/api/v1/bookings/{booking_id}/cancel",
                        headers=_auth(passenger_token))
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 7. MESSAGES
# ══════════════════════════════════════════════════════════════════════════════

class TestMessages:
    def _setup_with_booking(self, client):
        _register(client, email="driver2@test.com", first="D", last="R")
        driver_token = _login(client, email="driver2@test.com")
        trip_r = client.post("/api/v1/trips", headers=_auth(driver_token), json={
            "origin_city": "Leeds", "destination_city": "Sheffield",
            "departure_time": _future_dt(24), "price_per_seat": 8.00,
            "available_seats": 2, "vehicle_make": "VW",
            "vehicle_model": "Golf", "vehicle_color": "Grey",
        })
        trip_id = trip_r.json()["id"]
        _register(client, email="pax2@test.com", first="P", last="X")
        pax_token = _login(client, email="pax2@test.com")
        booking_r = client.post("/api/v1/bookings", headers=_auth(pax_token),
                                json={"trip_id": trip_id, "seats": 1})
        booking_id = booking_r.json()["id"]
        return driver_token, pax_token, booking_id

    def test_send_and_get_messages(self, client):
        driver_token, pax_token, booking_id = self._setup_with_booking(client)
        r = client.post(f"/api/v1/messages/{booking_id}",
                        headers=_auth(driver_token), json={"content": "See you at 9!"})
        assert r.status_code == 201, r.text
        r2 = client.get(f"/api/v1/messages/{booking_id}", headers=_auth(pax_token))
        assert r2.status_code == 200
        assert len(r2.json()) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# 8. REVIEWS
# ══════════════════════════════════════════════════════════════════════════════

class TestReviews:
    def test_list_reviews_for_user(self, client):
        data = _register(client)
        user_id = data["user"]["id"]
        token = _login(client)
        r = client.get(f"/api/v1/reviews/user/{user_id}", headers=_auth(token))
        assert r.status_code == 200
        assert r.json() == []


# ══════════════════════════════════════════════════════════════════════════════
# 9. NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════

class TestNotifications:
    def test_list_notifications_empty(self, client):
        _register(client)
        token = _login(client)
        r = client.get("/api/v1/notifications", headers=_auth(token))
        assert r.status_code == 200
        assert r.json() == []

    def test_register_device(self, client):
        _register(client)
        token = _login(client)
        r = client.post("/api/v1/notifications/devices/register",
                        headers=_auth(token),
                        json={"device_token": "fcm-test-token-abc", "platform": "ios"})
        assert r.status_code in (200, 201), r.text


# ══════════════════════════════════════════════════════════════════════════════
# 10. PAYMENTS
# ══════════════════════════════════════════════════════════════════════════════

class TestPayments:
    def test_payment_history_empty(self, client):
        _register(client)
        token = _login(client)
        r = client.get("/api/v1/payments/history?period=30d", headers=_auth(token))
        assert r.status_code == 200
        assert r.json() == []

    def test_payment_intent_unknown_booking(self, client):
        _register(client)
        token = _login(client)
        import uuid
        r = client.post("/api/v1/payments/intent",
                        headers=_auth(token),
                        json={"booking_id": str(uuid.uuid4())})
        assert r.status_code in (400, 404)  # service raises ValueError → 400


# ══════════════════════════════════════════════════════════════════════════════
# 11. ADMIN API
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminAPI:
    def _admin_token(self, client):
        _make_admin()
        return _login(client, email="admin@test.com", password="AdminPass1!")

    def test_admin_list_users(self, client):
        token = self._admin_token(client)
        r = client.get("/api/v1/admin/users", headers=_auth(token))
        assert r.status_code == 200

    def test_admin_metrics(self, client):
        token = self._admin_token(client)
        r = client.get("/api/v1/admin/metrics", headers=_auth(token))
        assert r.status_code == 200

    def test_admin_list_trips(self, client):
        token = self._admin_token(client)
        r = client.get("/api/v1/admin/trips", headers=_auth(token))
        assert r.status_code == 200

    def test_admin_list_bookings(self, client):
        token = self._admin_token(client)
        r = client.get("/api/v1/admin/bookings", headers=_auth(token))
        assert r.status_code == 200

    def test_non_admin_blocked(self, client):
        _register(client)
        token = _login(client)
        r = client.get("/api/v1/admin/users", headers=_auth(token))
        assert r.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# 12. ADMIN WEB DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminDashboard:
    def _admin_cookie(self, client) -> dict:
        """Log in via the login form and return a cookies dict."""
        _make_admin()
        r = client.post("/admin/login",
                        data={"email": "admin@test.com", "password": "AdminPass1!"},
                        follow_redirects=False)
        assert r.status_code == 303, r.text
        return dict(client.cookies)

    def test_dashboard_requires_auth(self, client):
        # Without a session cookie, redirect to /admin/login
        r = client.get("/admin/", follow_redirects=False)
        assert r.status_code == 303
        assert "/admin/login" in r.headers["location"]

    def test_login_page_loads(self, client):
        r = client.get("/admin/login")
        assert r.status_code == 200
        assert b"Rideway" in r.content

    def test_dashboard_loads(self, client):
        cookies = self._admin_cookie(client)
        r = client.get("/admin/", cookies=cookies)
        assert r.status_code == 200
        assert b"Rideway" in r.content

    def test_verification_page_loads(self, client):
        cookies = self._admin_cookie(client)
        r = client.get("/admin/verification", cookies=cookies)
        assert r.status_code == 200
        assert b"Verification" in r.content

    def test_users_page_loads(self, client):
        cookies = self._admin_cookie(client)
        r = client.get("/admin/users", cookies=cookies)
        assert r.status_code == 200

    def test_approve_unknown_user(self, client):
        cookies = self._admin_cookie(client)
        import uuid
        r = client.post(f"/admin/users/{uuid.uuid4()}/approve",
                        cookies=cookies, follow_redirects=False)
        assert r.status_code in (200, 303)

    def test_reject_unknown_user(self, client):
        cookies = self._admin_cookie(client)
        import uuid
        r = client.post(f"/admin/users/{uuid.uuid4()}/reject",
                        data={"reason": "Documents unclear"},
                        cookies=cookies, follow_redirects=False)
        assert r.status_code in (200, 303)


# ══════════════════════════════════════════════════════════════════════════════
# 13. AUTH GUARDS — unauthenticated access returns 401
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# TICKETS
# ══════════════════════════════════════════════════════════════════════════════

class TestTickets:
    def test_raise_ticket(self, client):
        _register(client)
        token = _login(client)
        r = client.post("/api/v1/tickets", headers=_auth(token), json={
            "category": "MISCONDUCT",
            "subject": "Driver was rude",
            "description": "The driver used abusive language during the trip.",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["category"] == "MISCONDUCT"
        assert data["status"] == "OPEN"
        assert data["admin_note"] is None

    def test_my_tickets(self, client):
        _register(client)
        token = _login(client)
        client.post("/api/v1/tickets", headers=_auth(token), json={
            "category": "FRAUD",
            "subject": "Overcharged for the trip",
            "description": "Driver charged more than the agreed price.",
        })
        r = client.get("/api/v1/tickets/me", headers=_auth(token))
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_get_ticket(self, client):
        _register(client)
        token = _login(client)
        c = client.post("/api/v1/tickets", headers=_auth(token), json={
            "category": "SAFETY",
            "subject": "Driver was speeding",
            "description": "The driver was doing 100mph on a 70mph road.",
        })
        ticket_id = c.json()["id"]
        r = client.get(f"/api/v1/tickets/{ticket_id}", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["id"] == ticket_id

    def test_cannot_get_other_users_ticket(self, client):
        _register(client)
        token = _login(client)
        c = client.post("/api/v1/tickets", headers=_auth(token), json={
            "category": "OTHER",
            "subject": "Test ticket",
            "description": "This ticket belongs to user A.",
        })
        ticket_id = c.json()["id"]
        _register(client, email="other@test.com")
        other_token = _login(client, email="other@test.com")
        r = client.get(f"/api/v1/tickets/{ticket_id}", headers=_auth(other_token))
        assert r.status_code == 404

    def test_admin_list_tickets(self, client):
        _make_admin()
        admin_token = _login(client, email="admin@test.com", password="AdminPass1!")
        r = client.get("/api/v1/tickets/admin/all", headers=_auth(admin_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_update_ticket(self, client):
        _register(client)
        token = _login(client)
        c = client.post("/api/v1/tickets", headers=_auth(token), json={
            "category": "HARASSMENT",
            "subject": "Passenger was threatening",
            "description": "The passenger made threatening remarks during the journey.",
        })
        ticket_id = c.json()["id"]
        _make_admin()
        admin_token = _login(client, email="admin@test.com", password="AdminPass1!")
        r = client.patch(f"/api/v1/tickets/admin/{ticket_id}", headers=_auth(admin_token), json={
            "status": "IN_PROGRESS",
            "admin_note": "We are reviewing your report and will respond within 24 hours.",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "IN_PROGRESS"
        assert "24 hours" in r.json()["admin_note"]

    def test_non_admin_cannot_list_all_tickets(self, client):
        _register(client)
        token = _login(client)
        r = client.get("/api/v1/tickets/admin/all", headers=_auth(token))
        assert r.status_code == 403


class TestAuthGuards:
    @pytest.mark.parametrize("method,url", [
        ("GET",  "/api/v1/users/me"),
        ("PUT",  "/api/v1/users/me"),
        ("GET",  "/api/v1/users/me/referral"),
        ("GET",  "/api/v1/users/me/vehicles"),
        ("POST", "/api/v1/trips"),
        ("GET",  "/api/v1/bookings/me"),
        ("GET",  "/api/v1/notifications"),
        ("GET",  "/api/v1/payments/history?period=30d"),
        ("GET",  "/api/v1/admin/users"),
        ("GET",  "/api/v1/admin/metrics"),
    ])
    def test_requires_auth(self, client, method, url):
        r = client.request(method, url)
        assert r.status_code == 401, f"{method} {url} → expected 401, got {r.status_code}"
