"""Apple Sign in with Apple server-to-server helpers.

Two jobs:
1. Exchange the one-time ``authorization_code`` from sign-in for a refresh
   token, which is what we store (the authorization code itself expires within
   minutes and cannot be revoked directly).
2. Revoke that refresh token on demand, as described in App Store Review
   Guideline 5.1.1(v) and Apple TN3194.

All calls are best-effort: sign-in must not fail because Apple is unreachable.
"""

import json
import logging
import time
import urllib.parse
import urllib.request

from app.core.config import get_settings

logger = logging.getLogger(__name__)

APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
APPLE_REVOKE_URL = "https://appleid.apple.com/auth/revoke"
APPLE_ISSUER = "https://appleid.apple.com"
# Apple rejects client secrets with an expiry further out than six months.
CLIENT_SECRET_TTL_SECONDS = 15777000


def is_configured() -> bool:
    """True when the Apple key material needed for server calls is present."""
    settings = get_settings()
    return bool(settings.apple_team_id and settings.apple_key_id and settings.apple_private_key)


def _client_secret() -> str:
    from jose import jwt as jose_jwt

    settings = get_settings()
    private_key = settings.apple_private_key.replace("\\n", "\n")
    now = int(time.time())
    claims = {
        "iss": settings.apple_team_id,
        "iat": now,
        "exp": now + CLIENT_SECRET_TTL_SECONDS,
        "aud": APPLE_ISSUER,
        "sub": settings.apple_bundle_id,
    }
    return jose_jwt.encode(
        claims,
        private_key,
        algorithm="ES256",
        headers={"kid": settings.apple_key_id},
    )


def _post(url: str, payload: dict) -> dict:
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode()
    return json.loads(body) if body else {}


def exchange_authorization_code(authorization_code: str) -> str | None:
    """Return the refresh token for a sign-in authorization code, or None.

    Returns None when Apple credentials are missing or the exchange fails.
    """
    if not is_configured():
        logger.warning("Apple credentials not configured — skipping authorization code exchange")
        return None
    try:
        result = _post(
            APPLE_TOKEN_URL,
            {
                "client_id": get_settings().apple_bundle_id,
                "client_secret": _client_secret(),
                "code": authorization_code,
                "grant_type": "authorization_code",
            },
        )
    except Exception as exc:
        logger.warning("Apple authorization code exchange failed: %s", exc)
        return None
    return result.get("refresh_token")


def revoke_token(token: str, token_type_hint: str = "refresh_token") -> bool:
    """Revoke one of Apple's refresh/access tokens. Never raises.

    Apple returns 200 both when the token is revoked and when it was already
    invalid, so a 2xx response is treated as success.
    """
    if not is_configured():
        logger.warning("Apple credentials not configured — skipping token revocation")
        return False
    try:
        _post(
            APPLE_REVOKE_URL,
            {
                "client_id": get_settings().apple_bundle_id,
                "client_secret": _client_secret(),
                "token": token,
                "token_type_hint": token_type_hint,
            },
        )
        return True
    except Exception as exc:
        logger.warning("Apple token revocation failed: %s", exc)
        return False
