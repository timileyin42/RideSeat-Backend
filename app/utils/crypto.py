"""GDPR-compliant field-level encryption for sensitive personal data.

Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
Set FIELD_ENCRYPTION_KEY env var to a valid Fernet key to enable encryption.
Generate a key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
If the env var is absent, values are stored unencrypted (safe for local dev and tests).
"""

from datetime import date as _date

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

import os


def _fernet() -> Fernet | None:
    key = os.getenv("FIELD_ENCRYPTION_KEY", "")
    if not key:
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedString(TypeDecorator):
    """Transparently encrypts/decrypts string columns at rest."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        f = _fernet()
        if f:
            return f.encrypt(str(value).encode()).decode()
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        f = _fernet()
        if f:
            try:
                return f.decrypt(value.encode()).decode()
            except (InvalidToken, Exception):
                return value  # legacy unencrypted row — return as-is
        return value


class EncryptedDate(TypeDecorator):
    """Transparently encrypts/decrypts date columns (stored as ISO strings) at rest."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        date_str = value.isoformat() if hasattr(value, "isoformat") else str(value)
        f = _fernet()
        if f:
            return f.encrypt(date_str.encode()).decode()
        return date_str

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        f = _fernet()
        raw = value
        if f:
            try:
                raw = f.decrypt(value.encode()).decode()
            except (InvalidToken, Exception):
                raw = value  # legacy unencrypted row
        try:
            return _date.fromisoformat(raw)
        except (ValueError, TypeError):
            return None
