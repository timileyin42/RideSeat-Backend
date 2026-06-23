"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, rate_limit
from app.core.security import create_access_token, create_refresh_token, decode_refresh_token
from app.schemas.auth import (
    AuthTokenResponse,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    GoogleMobileAuthRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResendOTPRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.schemas.base import DataResponse
from app.services.auth_service import AuthService
from app.repositories.user_repo import UserRepository
from app.services.email_service import EmailService

router = APIRouter()
auth_service = AuthService(UserRepository(), EmailService())


@router.post("/register", response_model=DataResponse[AuthTokenResponse], status_code=201)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    _=Depends(rate_limit("auth_register", limit=5, window_seconds=60)),
):
    try:
        user, access_token, refresh_token = auth_service.register(
            db,
            email=payload.email,
            password=payload.password,
        )
        db.commit()
        return DataResponse(data=AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/login",
    response_model=DataResponse[AuthTokenResponse],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["email", "password"],
                        "properties": {
                            "email": {"type": "string", "format": "email"},
                            "password": {"type": "string"},
                        },
                    },
                    "example": {
                        "email": "james.harrison@example.com",
                        "password": "SecurePass1!",
                    },
                }
            },
        }
    },
)
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
        return DataResponse(data=AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/google", response_model=DataResponse[AuthTokenResponse])
def google_auth(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    try:
        user, access_token, refresh_token = auth_service.google_auth(db, payload.id_token)
        db.commit()
        return DataResponse(data=AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/google/mobile", response_model=DataResponse[AuthTokenResponse])
def google_mobile_auth(
    payload: GoogleMobileAuthRequest,
    db: Session = Depends(get_db),
    _=Depends(rate_limit("auth_google_mobile", limit=10, window_seconds=60)),
):
    try:
        user, access_token, refresh_token = auth_service.google_auth(db, payload.id_token)
        db.commit()
        return DataResponse(data=AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/verify-email", response_model=DataResponse[AuthTokenResponse])
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    try:
        user, access_token, refresh_token = auth_service.verify_email(db, payload.email, payload.token)
        db.commit()
        return DataResponse(data=AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/resend-otp")
def resend_otp(
    payload: ResendOTPRequest,
    db: Session = Depends(get_db),
    _=Depends(rate_limit("auth_resend_otp", limit=3, window_seconds=60)),
):
    try:
        auth_service.resend_verify_otp(db, payload.email)
        return {"data": {"status": "sent"}}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
    _=Depends(rate_limit("auth_forgot_password", limit=5, window_seconds=60)),
):
    try:
        auth_service.forgot_password(db, payload.email)
        return {"data": {"status": "sent"}}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/token", include_in_schema=False)
async def swagger_token(
    request: Request,
    db: Session = Depends(get_db),
):
    """OAuth2-compatible endpoint for Swagger UI login. Returns flat {access_token, token_type}."""
    form = await request.form()
    email = form.get("username") or form.get("email")
    password = form.get("password")
    try:
        user, access_token, _ = auth_service.login(db, str(email), str(password))
        return {"access_token": access_token, "token_type": "bearer"}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    _=Depends(rate_limit("auth_reset_password", limit=5, window_seconds=60)),
):
    try:
        auth_service.reset_password(db, payload.email, payload.token, payload.new_password)
        db.commit()
        return {"data": {"status": "reset"}}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/refresh", response_model=DataResponse[AuthTokenResponse])
def refresh_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
    _=Depends(rate_limit("auth_refresh", limit=20, window_seconds=60)),
):
    try:
        from uuid import UUID
        token_data = decode_refresh_token(payload.refresh_token)
        user_id = UUID(token_data["sub"])
        user_repo = auth_service.user_repo
        user = user_repo.get_by_id(db, user_id)
        if not user or not user.is_active:
            raise ValueError("User not found")
        access_token = create_access_token(str(user.id))
        new_refresh_token = create_refresh_token(str(user.id))
        return DataResponse(data=AuthTokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            user=user,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
