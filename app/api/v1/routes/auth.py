"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, rate_limit
from app.core.security import create_access_token, create_refresh_token, decode_refresh_token
from app.schemas.auth import (
    AuthTokenResponse,
    ChangePasswordRequest,
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
from app.schemas.user import UserPrivateResponse
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
            first_name=payload.first_name,
            last_name=payload.last_name,
            date_of_birth=payload.date_of_birth,
        )
        db.commit()
        user_response = UserPrivateResponse.model_validate(user).model_copy(update={"is_new_user": True})
        return DataResponse(data=AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user_response))
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
        user_response = UserPrivateResponse.model_validate(user).model_copy(update={"is_new_user": False})
        return DataResponse(data=AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user_response))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/google", response_model=DataResponse[AuthTokenResponse])
def google_auth(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    try:
        user, access_token, refresh_token, is_new_user = auth_service.google_auth(db, payload.id_token)
        db.commit()
        user_response = UserPrivateResponse.model_validate(user).model_copy(update={"is_new_user": is_new_user})
        return DataResponse(data=AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user_response))
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
        user, access_token, refresh_token, is_new_user = auth_service.google_auth(db, payload.id_token)
        db.commit()
        user_response = UserPrivateResponse.model_validate(user).model_copy(update={"is_new_user": is_new_user})
        return DataResponse(data=AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user_response))
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


@router.get("/google/authorize")
def google_web_authorize(
    state: str | None = Query(default=None),
    redirect_uri: str | None = Query(default=None),
):
    """Redirect browser to Google OAuth consent screen for web sign-in."""
    try:
        from app.core.config import get_settings
        import urllib.parse as _parse
        settings = get_settings()
        if not settings.google_client_id:
            raise ValueError("Google OAuth not configured")
        effective_redirect = redirect_uri or getattr(settings, "google_web_redirect_uri", None)
        if not effective_redirect:
            raise ValueError("No redirect_uri configured for web OAuth")
        import secrets as _secrets
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": effective_redirect,
            "scope": "openid email profile",
            "response_type": "code",
            "state": state or _secrets.token_urlsafe(16),
            "access_type": "offline",
            "prompt": "select_account",
        }
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + _parse.urlencode(params)
        return RedirectResponse(url=url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/google/callback", response_model=DataResponse[AuthTokenResponse])
def google_web_callback(
    code: str = Query(...),
    state: str | None = Query(default=None),
    redirect_uri: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Exchange Google authorization code for app tokens (web redirect flow)."""
    try:
        import urllib.parse as _parse
        import urllib.request as _req
        import json as _json
        from app.core.config import get_settings
        settings = get_settings()
        effective_redirect = redirect_uri or getattr(settings, "google_web_redirect_uri", None)
        if not effective_redirect:
            raise ValueError("No redirect_uri configured for web OAuth")

        # Exchange code → id_token via Google token endpoint
        token_payload = _parse.urlencode({
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": effective_redirect,
            "grant_type": "authorization_code",
        }).encode()
        req = _req.Request(
            "https://oauth2.googleapis.com/token",
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with _req.urlopen(req, timeout=10) as resp:
            token_data = _json.loads(resp.read())

        id_token_str = token_data.get("id_token")
        if not id_token_str:
            raise ValueError("Google did not return an id_token")

        user, access_token, refresh_token, is_new_user = auth_service.google_auth(db, id_token_str)
        db.commit()
        user_response = UserPrivateResponse.model_validate(user).model_copy(update={"is_new_user": is_new_user})
        return DataResponse(data=AuthTokenResponse(access_token=access_token, refresh_token=refresh_token, user=user_response))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail="Google token exchange failed") from exc


@router.post("/change-password", response_model=DataResponse[dict])
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("auth_change_password", limit=5, window_seconds=60)),
):
    """Change password from within the app settings. Requires current password."""
    try:
        auth_service.change_password(db, current_user, payload.current_password, payload.new_password)
        db.commit()
        return DataResponse(data={"message": "Password changed successfully"})
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/firebase-token", response_model=DataResponse[dict])
def get_firebase_token(
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("auth_firebase_token", limit=10, window_seconds=60)),
):
    """Mint a Firebase custom token for the logged-in user.

    Web clients use this to authenticate with Firestore after logging in via
    the standard JWT flow. Call once after login, then:
      signInWithCustomToken(auth, firebaseToken)
    """
    from app.core.config import get_settings
    from app.services.notification_service import _get_firebase_app

    settings = get_settings()
    if not settings.gcp_credentials_json:
        raise HTTPException(status_code=503, detail="Firebase not configured")
    try:
        from firebase_admin import auth as fb_auth
        app = _get_firebase_app(settings.gcp_credentials_json)
        token = fb_auth.create_custom_token(str(current_user.id), app=app)
        # create_custom_token returns bytes — decode to string for JSON
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return DataResponse(data={"firebase_token": token})
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not mint Firebase token") from exc
