"""Admin web dashboard — served at /admin/, protected by HTTP Basic Auth."""

import secrets
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.repositories.user_repo import UserRepository
from app.services.email_service import EmailService
from app.services.storage_service import StorageService
from app.services.user_service import UserService
from app.repositories.booking_repo import BookingRepository

router = APIRouter()
_security = HTTPBasic()
_templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))
_user_repo = UserRepository()
_user_service = UserService(UserRepository(), BookingRepository())
_storage = StorageService()


def _require_admin(credentials: HTTPBasicCredentials = Depends(_security)):
    settings = get_settings()
    ok_user = secrets.compare_digest(credentials.username.encode(), settings.admin_email.encode())
    ok_pass = secrets.compare_digest(credentials.password.encode(), settings.admin_password.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="Unauthorised",
            headers={"WWW-Authenticate": "Basic"},
        )


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    flash: str | None = None,
    _=Depends(_require_admin),
):
    db = SessionLocal()
    try:
        users = _user_repo.list_pending_verifications(db)
    finally:
        db.close()

    # Generate 15-minute signed URLs for private KYC documents
    def _sign(url: str | None) -> str | None:
        if not url:
            return None
        try:
            return _storage.signed_url(url, expiry_minutes=15)
        except Exception:
            return url  # fall back to raw path if signing fails

    signed_users = [
        {
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
            "driver_license_number": u.driver_license_number,
            "licence_url": _sign(u.driver_license_url),
            "selfie_url": _sign(u.selfie_url),
            "id_document_url": _sign(u.id_document_url),
        }
        for u in users
    ]

    flash_ok = flash if flash and not flash.startswith("ERR:") else None
    flash_err = flash[4:] if flash and flash.startswith("ERR:") else None

    return _templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context={"users": signed_users, "flash_ok": flash_ok, "flash_err": flash_err},
    )


@router.post("/users/{user_id}/approve")
def approve(user_id: UUID, _=Depends(_require_admin)):
    db = SessionLocal()
    try:
        admin = _user_repo.get_by_email(db, get_settings().admin_email)
        if not admin:
            return RedirectResponse("/admin/?flash=ERR:Admin+user+not+found", status_code=303)
        _user_service.approve_identity(db, admin, user_id, email_service=EmailService())
        db.commit()
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(f"/admin/?flash=ERR:{str(exc).replace(' ', '+')}", status_code=303)
    finally:
        db.close()
    return RedirectResponse("/admin/?flash=Driver+approved+successfully", status_code=303)


@router.post("/users/{user_id}/reject")
def reject(user_id: UUID, reason: str | None = Form(default=None), _=Depends(_require_admin)):
    db = SessionLocal()
    try:
        admin = _user_repo.get_by_email(db, get_settings().admin_email)
        if not admin:
            return RedirectResponse("/admin/?flash=ERR:Admin+user+not+found", status_code=303)
        _user_service.reject_identity(db, admin, user_id, reason=reason or None, email_service=EmailService())
        db.commit()
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(f"/admin/?flash=ERR:{str(exc).replace(' ', '+')}", status_code=303)
    finally:
        db.close()
    return RedirectResponse("/admin/?flash=Driver+rejected", status_code=303)
