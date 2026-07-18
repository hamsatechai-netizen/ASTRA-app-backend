"""
User identity repository contract.

Backs the existing `hamsatech.users` table (see `app.models.hamsatech_user`).
Narrow by design (Interface Segregation, same rationale as
`OTPRepositoryInterface`): only the phone-identity operations Phase 3
needs, nothing about the wider `hamsatech` schema.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.models.hamsatech_user import HamsaTechUser


class UserRepositoryInterface(ABC):
    """Abstract contract for reading and persisting phone-verified user identities."""

    @abstractmethod
    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        """Return the user identity for `phone_number`, or None if no account exists."""

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> HamsaTechUser | None:
        """Return the user identity for `user_id`, or None if no account exists."""

    @abstractmethod
    async def create(self, phone_number: str) -> HamsaTechUser:
        """Create a new user identity for `phone_number` with the minimum required fields."""

    @abstractmethod
    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        """Set `phone_verified_at` and `last_login_at` on `user` to the current time."""
