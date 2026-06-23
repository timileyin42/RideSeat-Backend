"""Application entry point."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.api.admin_web import router as admin_web_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repo import UserRepository


def create_app() -> FastAPI:
    app = FastAPI(
        title="Rideway API",
        description=(
            "**Authentication:** Click **Authorize** (top right), enter your email in the "
            "`username` field and your password, then click **Authorize**. "
            "All protected endpoints will use that token automatically."
        ),
        version="1.0.0",
    )
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        if errors:
            first = errors[0]
            field = ".".join(str(loc) for loc in first.get("loc", []) if loc not in ("body", "query"))
            msg = first.get("msg", "Validation error")
            detail = f"{field}: {msg}" if field else msg
        else:
            detail = "Invalid request"
        return JSONResponse(status_code=422, content={"data": None, "error": detail})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"data": None, "error": exc.detail})

    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
    app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    def root(request: Request):
        return templates.TemplateResponse(request=request, name="landing.html")
    @app.get("/health")
    def health():
        return {"status": "ok"}
    @app.on_event("startup")
    def bootstrap_admin():
        settings = get_settings()
        if not settings.admin_email or not settings.admin_password:
            return
        db = SessionLocal()
        try:
            user_repo = UserRepository()
            existing = user_repo.get_by_email(db, settings.admin_email)
            if existing:
                if existing.is_admin:
                    print("Admin user already exists")
                    return
                existing.is_admin = True
                existing.is_email_verified = True
                user_repo.update(db, existing)
                db.commit()
                print("Existing user promoted to admin")
                return
            admin_user = User(
                first_name=settings.admin_first_name or "Admin",
                last_name=settings.admin_last_name or "User",
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
                is_email_verified=True,
            )
            try:
                user_repo.create(db, admin_user)
                db.commit()
                print("Admin user created")
            except Exception:
                # Another worker already inserted — safe to ignore
                db.rollback()
        finally:
            db.close()
    app.include_router(api_router)
    app.include_router(admin_web_router, prefix="/admin")
    return app


app = create_app()
