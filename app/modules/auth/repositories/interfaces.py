"""
Auth repository contract (Repository Pattern).

Unlike the project-wide `BaseRepository[ModelType]` (which takes a
SQLAlchemy `AsyncSession` directly), this interface does not commit to a
storage technology in its constructor. Whether Phase 2 backs this with
direct Postgres access (SQLAlchemy) or the Supabase Auth API depends on a
decision not yet made — this interface only fixes *what* the service
layer needs, not *how* it's fetched. No queries, no concrete class, no
persistence logic.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class AuthRepositoryInterface(ABC):
    """Abstract contract for looking up and persisting auth-related state."""

    @abstractmethod
    async def get_athlete_by_phone(self, phone_number: str) -> Any | None:
        """Return the athlete record for `phone_number`, or None if no account exists."""

    @abstractmethod
    async def create_athlete(self, phone_number: str) -> Any:
        """Create and return a new athlete record for `phone_number`."""

    @abstractmethod
    async def save_otp(self, phone_number: str, otp_code: str, expires_at: datetime) -> None:
        """Persist a newly generated OTP challenge for `phone_number`."""

    @abstractmethod
    async def get_active_otp(self, phone_number: str) -> Any | None:
        """Return the current unexpired OTP challenge for `phone_number`, if any."""

    @abstractmethod
    async def increment_otp_attempts(self, phone_number: str) -> int:
        """Increment and return the verification-attempt counter for `phone_number`'s active OTP."""

    @abstractmethod
    async def invalidate_otp(self, phone_number: str) -> None:
        """Invalidate `phone_number`'s active OTP (consumed or superseded)."""
