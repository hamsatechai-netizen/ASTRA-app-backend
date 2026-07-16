"""
JWT generation/validation utilities.

Pure infrastructure: encoding and decoding signed tokens using this
project's algorithm/secret/expiry conventions. Deciding *who* gets a
token and *when* is Phase 2 business logic (`TokenService`); these
functions only wrap PyJWT so the rest of the module never imports it
directly or handles its exception types.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from app.config.settings import get_settings
from app.modules.auth.constants import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.modules.auth.exceptions import InvalidTokenException
from app.modules.auth.security.expiry import utc_expiry
from app.utils.datetime import utc_now


def _encode(subject: UUID, expires_at: datetime, token_type: str) -> str:
    settings = get_settings()
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": utc_now(),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_access_token(subject: UUID, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    """Encode a short-lived access token for `subject` (the athlete's ID)."""
    return _encode(subject, utc_expiry(expires_minutes * 60), token_type="access")


def create_refresh_token(subject: UUID, expires_days: int = REFRESH_TOKEN_EXPIRE_DAYS) -> str:
    """Encode a long-lived refresh token for `subject` (the athlete's ID)."""
    return _encode(subject, utc_expiry(expires_days * 24 * 60 * 60), token_type="refresh")


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify `token`'s signature and expiry, returning its claims.

    Raises `InvalidTokenException` for any malformed, expired, or
    signature-invalid token, so callers never need to know about PyJWT's
    own exception hierarchy.
    """
    settings = get_settings()
    try:
        claims: dict[str, Any] = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except InvalidTokenError as exc:
        raise InvalidTokenException() from exc
    return claims
