"""Application entry point."""

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repo import UserRepository


def create_app() -> FastAPI:
    app = FastAPI(title="RideSeat API")
    @app.get("/")
    def root():
        return {"message": "Welcome to RideSeat Backend", "docs": "/docs", "redoc": "/redoc"}
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
            user_repo.create(db, admin_user)
            db.commit()
            print("Admin user created")
        finally:
            db.close()
    app.include_router(api_router)
    return app


app = create_app()
