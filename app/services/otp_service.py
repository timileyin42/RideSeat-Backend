"""Redis-backed OTP storage with automatic TTL expiry.

OTPs are stored as:
  rideway:otp:verify:{email}  → 6-digit code, TTL 10 min
  rideway:otp:reset:{email}   → 6-digit code, TTL 10 min

Redis deletes the key automatically when TTL expires — no manual cleanup needed.
If the user doesn't verify within 10 minutes, the key is gone and they must
request a new OTP.
"""

import redis

from app.core.config import get_settings

_TTL = 600  # 10 minutes in seconds
_KEY_VERIFY = "rideway:otp:verify:{}"
_KEY_RESET = "rideway:otp:reset:{}"


def _client() -> redis.Redis:
    settings = get_settings()
    # Re-use the same Redis instance as Celery, but on DB 2 (separate from queues)
    base_url = settings.celery_broker_url.rsplit("/", 1)[0]
    return redis.from_url(f"{base_url}/2", decode_responses=True)


# ── email verification ─────────────────────────────────────────────────────────

def save_verify_otp(email: str, otp: str) -> None:
    _client().setex(_KEY_VERIFY.format(email.lower()), _TTL, otp)


def get_verify_otp(email: str) -> str | None:
    return _client().get(_KEY_VERIFY.format(email.lower()))


def delete_verify_otp(email: str) -> None:
    _client().delete(_KEY_VERIFY.format(email.lower()))


# ── password reset ─────────────────────────────────────────────────────────────

def save_reset_otp(email: str, otp: str) -> None:
    _client().setex(_KEY_RESET.format(email.lower()), _TTL, otp)


def get_reset_otp(email: str) -> str | None:
    return _client().get(_KEY_RESET.format(email.lower()))


def delete_reset_otp(email: str) -> None:
    _client().delete(_KEY_RESET.format(email.lower()))
