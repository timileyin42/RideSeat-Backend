"""Redis-backed OTP storage with automatic TTL expiry.

OTPs are stored as:
  rideway:otp:verify:{email}       → 6-digit code, TTL 10 min
  rideway:otp:reset:{email}        → 6-digit code, TTL 10 min
  rideway:otp:phone_channel:{phone} → attempt number (1-3), TTL 10 min
                                      1=SMS, 2=WhatsApp, 3=Voice

Redis deletes keys automatically when TTL expires — no manual cleanup needed.
"""

import redis

from app.core.config import get_settings

_TTL = 600  # 10 minutes in seconds
_KEY_VERIFY = "rideway:otp:verify:{}"
_KEY_RESET = "rideway:otp:reset:{}"
_KEY_PHONE_CHANNEL = "rideway:otp:phone_channel:{}"

# Ordered delivery channels — each resend escalates to the next
PHONE_CHANNELS = ["sms", "whatsapp", "voice"]


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


# ── phone OTP channel tracking ────────────────────────────────────────────────

def next_phone_channel(phone: str) -> str:
    """Return the next delivery channel and advance the counter.

    First call  → "sms"
    Second call → "whatsapp"
    Third call  → "voice"
    Fourth call → cycles back to "sms" (starts fresh)
    """
    key = _KEY_PHONE_CHANNEL.format(phone)
    client = _client()
    raw = client.get(key)
    attempt = int(raw) if raw else 0
    channel = PHONE_CHANNELS[attempt % len(PHONE_CHANNELS)]
    client.setex(key, _TTL, attempt + 1)
    return channel


def reset_phone_channel(phone: str) -> None:
    """Clear the channel counter after successful verification."""
    _client().delete(_KEY_PHONE_CHANNEL.format(phone))
