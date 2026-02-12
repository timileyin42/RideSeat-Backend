"""Application configuration."""

from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_port: int
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    stripe_secret_key: str
    stripe_webhook_secret: str
    resend_api_key: str
    email_from: str
    frontend_base_url: str
    google_client_id: str
    google_client_secret: str
    gcp_project_id: str
    gcp_storage_bucket: str
    gcp_credentials_json: str
    admin_email: str
    admin_password: str
    admin_first_name: str
    admin_last_name: str
    celery_broker_url: str
    celery_result_backend: str
    spotify_playlist_url: str
    referral_base_url: str
    refresh_token_expire_days: int
    termii_api_key: str
    termii_sender_id: str
    termii_base_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "RideSeat API"),
        app_port=int(os.getenv("APP_PORT", "8000")),
        database_url=os.getenv("DATABASE_URL", ""),
        jwt_secret_key=os.getenv("JWT_SECRET_KEY", ""),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        stripe_secret_key=os.getenv("STRIPE_SECRET_KEY", ""),
        stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", ""),
        resend_api_key=os.getenv("RESEND_API_KEY", ""),
        email_from=os.getenv("EMAIL_FROM", ""),
        frontend_base_url=os.getenv("FRONTEND_BASE_URL", ""),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        gcp_project_id=os.getenv("GCP_PROJECT_ID", ""),
        gcp_storage_bucket=os.getenv("GCP_STORAGE_BUCKET", ""),
        gcp_credentials_json=os.getenv("GCP_CREDENTIALS_JSON", ""),
        admin_email=os.getenv("ADMIN_EMAIL", ""),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
        admin_first_name=os.getenv("ADMIN_FIRST_NAME", "Admin"),
        admin_last_name=os.getenv("ADMIN_LAST_NAME", "User"),
        celery_broker_url=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
        celery_result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
        spotify_playlist_url=os.getenv("SPOTIFY_PLAYLIST_URL", ""),
        referral_base_url=os.getenv("REFERRAL_BASE_URL", ""),
        refresh_token_expire_days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30")),
        termii_api_key=os.getenv("TERMII_API_KEY", ""),
        termii_sender_id=os.getenv("TERMII_SENDER_ID", ""),
        termii_base_url=os.getenv("TERMII_BASE_URL", "https://api.ng.termii.com"),
    )
