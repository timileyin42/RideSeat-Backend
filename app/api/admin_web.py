"""Admin web dashboard — login page + session cookie auth."""

import hmac
import hashlib
import secrets
import time
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.services.admin_service import AdminService
from app.services.email_service import EmailService
from app.services.storage_service import StorageService
from app.services.user_service import UserService

router = APIRouter()
_templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))
_user_repo = UserRepository()
_user_service = UserService(UserRepository(), BookingRepository())
_admin_service = AdminService(UserRepository(), TripRepository(), BookingRepository(), PaymentRepository())
_storage = StorageService()

_SESSION_TTL = 8 * 60 * 60  # 8 hours


# ── session helpers ────────────────────────────────────────────────────────────

def _make_token() -> str:
    settings = get_settings()
    ts = str(int(time.time()))
    nonce = secrets.token_hex(16)
    payload = f"{ts}.{nonce}"
    sig = hmac.new(settings.jwt_secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _verify_token(token: str) -> bool:
    try:
        settings = get_settings()
        ts_str, nonce, sig = token.split(".", 2)
        payload = f"{ts_str}.{nonce}"
        expected = hmac.new(settings.jwt_secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return False
        return time.time() - int(ts_str) <= _SESSION_TTL
    except Exception:
        return False


def _require_session(admin_session: str | None = Cookie(default=None)):
    if not admin_session or not _verify_token(admin_session):
        return None
    return admin_session


# ── shared context helper ──────────────────────────────────────────────────────

def _base_ctx(db, active: str) -> dict:
    """Shared context injected into every template (pending count for nav badge)."""
    pending = _user_repo.list_pending_verifications(db)
    return {"active": active, "pending_count": len(pending)}


# ── login / logout ─────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, admin_session: str | None = Cookie(default=None)):
    if admin_session and _verify_token(admin_session):
        return RedirectResponse("/admin/", status_code=303)
    return _templates.TemplateResponse(request=request, name="admin/login.html", context={})


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    settings = get_settings()
    ok = hmac.compare_digest(email.strip().lower(), settings.admin_email.lower()) and \
         hmac.compare_digest(password, settings.admin_password)
    if not ok:
        return _templates.TemplateResponse(
            request=request, name="admin/login.html",
            context={"error": "Invalid email or password.", "email": email},
            status_code=401,
        )
    response = RedirectResponse("/admin/", status_code=303)
    response.set_cookie("admin_session", _make_token(), max_age=_SESSION_TTL,
                        httponly=True, samesite="lax", secure=True)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie("admin_session")
    return response


# ── overview ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def overview(request: Request, session=Depends(_require_session)):
    if not session:
        return RedirectResponse("/admin/login", status_code=303)
    db = SessionLocal()
    try:
        admin = _user_repo.get_by_email(db, get_settings().admin_email)
        metrics = _admin_service.get_metrics(db, admin) if admin else {}
        recent_users = list(reversed(_user_repo.list_users(db, limit=10, offset=0)))
        ctx = _base_ctx(db, "overview")
    finally:
        db.close()
    return _templates.TemplateResponse(
        request=request, name="admin/overview.html",
        context={**ctx, "metrics": metrics, "recent_users": recent_users},
    )


# ── users list ─────────────────────────────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
def users_list(request: Request, session=Depends(_require_session)):
    if not session:
        return RedirectResponse("/admin/login", status_code=303)
    db = SessionLocal()
    try:
        all_users = _user_repo.list_users(db, limit=500, offset=0)
        ctx = _base_ctx(db, "users")
    finally:
        db.close()
    return _templates.TemplateResponse(
        request=request, name="admin/users.html",
        context={**ctx, "users": all_users, "total": len(all_users)},
    )


# ── verification queue ─────────────────────────────────────────────────────────

@router.get("/verification", response_class=HTMLResponse)
def verification_queue(
    request: Request,
    flash: str | None = None,
    session=Depends(_require_session),
):
    if not session:
        return RedirectResponse("/admin/login", status_code=303)
    db = SessionLocal()
    try:
        pending = _user_repo.list_pending_verifications(db)
        ctx = _base_ctx(db, "verification")
    finally:
        db.close()

    def _sign(url):
        if not url:
            return None
        try:
            return _storage.signed_url(url, expiry_minutes=15)
        except Exception:
            return url

    signed_users = [
        {
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
            "driver_license_number": u.driver_license_number,
            "licence_front_url": _sign(u.driver_license_url),
            "licence_back_url": _sign(u.driver_license_back_url),
            "selfie_url": _sign(u.selfie_url),
            "id_document_url": _sign(u.id_document_url),
        }
        for u in pending
    ]

    flash_ok = flash if flash and not flash.startswith("ERR:") else None
    flash_err = flash[4:] if flash and flash.startswith("ERR:") else None

    return _templates.TemplateResponse(
        request=request, name="admin/dashboard.html",
        context={**ctx, "users": signed_users, "flash_ok": flash_ok, "flash_err": flash_err},
    )


@router.post("/users/{user_id}/approve")
def approve(user_id: UUID, session=Depends(_require_session)):
    if not session:
        return RedirectResponse("/admin/login", status_code=303)
    db = SessionLocal()
    try:
        admin = _user_repo.get_by_email(db, get_settings().admin_email)
        if not admin:
            return RedirectResponse("/admin/verification?flash=ERR:Admin+not+found", status_code=303)
        _user_service.approve_identity(db, admin, user_id, email_service=EmailService())
        db.commit()
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(f"/admin/verification?flash=ERR:{str(exc).replace(' ', '+')}", status_code=303)
    finally:
        db.close()
    return RedirectResponse("/admin/verification?flash=Driver+approved+successfully", status_code=303)


@router.post("/users/{user_id}/reject")
def reject(user_id: UUID, reason: str | None = Form(default=None), session=Depends(_require_session)):
    if not session:
        return RedirectResponse("/admin/login", status_code=303)
    db = SessionLocal()
    try:
        admin = _user_repo.get_by_email(db, get_settings().admin_email)
        if not admin:
            return RedirectResponse("/admin/verification?flash=ERR:Admin+not+found", status_code=303)
        _user_service.reject_identity(db, admin, user_id, reason=reason or None, email_service=EmailService())
        db.commit()
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(f"/admin/verification?flash=ERR:{str(exc).replace(' ', '+')}", status_code=303)
    finally:
        db.close()
    return RedirectResponse("/admin/verification?flash=Driver+rejected", status_code=303)
