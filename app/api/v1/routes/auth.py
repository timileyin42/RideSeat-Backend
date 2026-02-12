"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, rate_limit
from app.schemas.auth import (
    AuthTokenResponse,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    GoogleMobileAuthRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.services.auth_service import AuthService
from app.repositories.user_repo import UserRepository
from app.services.email_service import EmailService

router = APIRouter()
auth_service = AuthService(UserRepository(), EmailService())


@router.post("/register", response_model=RegisterResponse)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    _=Depends(rate_limit("auth_register", limit=5, window_seconds=60)),
):
    try:
        user = auth_service.register(
            db,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password=payload.password,
            phone_number=payload.phone_number,
        )
        db.commit()
        return RegisterResponse(user_id=str(user.id), email=user.email, is_email_verified=user.is_email_verified)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    request: Request,
    db: Session = Depends(get_db),
    _=Depends(rate_limit("auth_login", limit=10, window_seconds=60)),
):
    try:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/x-www-form-urlencoded"):
            form = await request.form()
            email = form.get("username") or form.get("email")
            password = form.get("password")
        else:
            payload = LoginRequest(**(await request.json()))
            email = payload.email
            password = payload.password
        if not email or not password:
            raise ValueError("Invalid credentials")
        user, access_token, refresh_token = auth_service.login(db, email, password)
        return AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/google", response_model=AuthTokenResponse)
def google_auth(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    try:
        user, access_token, refresh_token = auth_service.google_auth(db, payload.id_token)
        db.commit()
        return AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/google/mobile", response_model=AuthTokenResponse)
def google_mobile_auth(
    payload: GoogleMobileAuthRequest,
    db: Session = Depends(get_db),
    _=Depends(rate_limit("auth_google_mobile", limit=10, window_seconds=60)),
):
    try:
        user, access_token, refresh_token = auth_service.google_auth(db, payload.id_token)
        db.commit()
        return AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/verify-email", response_model=AuthTokenResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    try:
        user, access_token, refresh_token = auth_service.verify_email(db, payload.token)
        db.commit()
        return AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
    _=Depends(rate_limit("auth_forgot_password", limit=5, window_seconds=60)),
):
    try:
        auth_service.forgot_password(db, payload.email)
        db.commit()
        return {"status": "sent"}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    _=Depends(rate_limit("auth_reset_password", limit=5, window_seconds=60)),
):
    try:
        auth_service.reset_password(db, payload.token, payload.new_password)
        db.commit()
        return {"status": "reset"}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
