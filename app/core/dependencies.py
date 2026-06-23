"""Dependency providers for database access, auth, and throttling."""

from collections.abc import Callable, Generator
from threading import Lock
from time import monotonic

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.repositories.user_repo import UserRepository

security = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
user_repo = UserRepository()
rate_limit_lock = Lock()
rate_limit_state: dict[str, list[float]] = {}


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        import sys
        print("DEBUG [get_current_user]: Token received:", repr(token), file=sys.stderr)
        token_data = decode_access_token(token)
        print("DEBUG [get_current_user]: Decoded token data:", token_data, file=sys.stderr)
        user_id = UUID(token_data["sub"])
        print("DEBUG [get_current_user]: User ID from token:", user_id, file=sys.stderr)
        user = user_repo.get_by_id(db, user_id)
        print("DEBUG [get_current_user]: Found user:", user, file=sys.stderr)
        if not user:
            print("DEBUG [get_current_user]: User not found!", file=sys.stderr)
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return user
    except Exception as exc:
        import sys
        import traceback
        print("DEBUG [get_current_user]: Exception:", str(exc), file=sys.stderr)
        print("DEBUG [get_current_user]: Traceback:", traceback.format_exc(), file=sys.stderr)
        raise HTTPException(status_code=401, detail="Invalid authentication credentials") from exc


def require_admin(
    token: str = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        token_data = decode_access_token(token)
        user_id = UUID(token_data["sub"])
        user = user_repo.get_by_id(db, user_id)
        if not user or not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        return user
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials") from exc


def rate_limit(name: str, limit: int, window_seconds: int) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        client_host = request.client.host if request.client else "unknown"
        key = f"{name}:{client_host}"
        now = monotonic()
        window_start = now - window_seconds
        with rate_limit_lock:
            timestamps = rate_limit_state.get(key, [])
            timestamps = [timestamp for timestamp in timestamps if timestamp > window_start]
            if len(timestamps) >= limit:
                raise HTTPException(status_code=429, detail="Too many requests")
            timestamps.append(now)
            rate_limit_state[key] = timestamps

    return dependency
