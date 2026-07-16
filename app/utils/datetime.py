"""UTC-only datetime helpers. All persisted/returned timestamps must be timezone-aware UTC."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)
