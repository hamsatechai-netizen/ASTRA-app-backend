"""Expiry-time arithmetic shared by the JWT and OTP utilities — no business logic, just UTC math."""

from datetime import datetime, timedelta

from app.utils.datetime import utc_now


def utc_expiry(seconds_from_now: int) -> datetime:
    """Return the UTC instant `seconds_from_now` seconds in the future."""
    return utc_now() + timedelta(seconds=seconds_from_now)


def is_expired(expires_at: datetime) -> bool:
    """Return True if `expires_at` (a UTC-aware datetime) is in the past."""
    return utc_now() >= expires_at
