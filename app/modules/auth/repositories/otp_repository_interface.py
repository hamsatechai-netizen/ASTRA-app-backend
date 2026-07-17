"""
OTP repository contract.

Deliberately narrow (Interface Segregation): OTP verification only ever
needs to read/write the current OTP challenge for a phone number, never
anything about a user/athlete account — see `UserRepositoryInterface` and
`AthleteProfileRepositoryInterface` for those.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from app.models.otp_challenge import OTPChallenge


class OTPRepositoryInterface(ABC):
    """Abstract contract for reading and persisting OTP challenges."""

    @abstractmethod
    async def get_by_phone(self, phone_number: str) -> OTPChallenge | None:
        """Return the current OTP challenge for `phone_number`, if any."""

    @abstractmethod
    async def upsert(self, phone_number: str, otp_hash: str, expires_at: datetime) -> OTPChallenge:
        """Create or overwrite the OTP challenge for `phone_number`, resetting its attempt counter to 0."""

    @abstractmethod
    async def increment_attempts(self, phone_number: str) -> int:
        """Increment and return the verification-attempt counter for `phone_number`'s active challenge."""

    @abstractmethod
    async def delete_by_phone(self, phone_number: str) -> None:
        """Delete the OTP challenge for `phone_number` (consumed on success, so it can never be replayed)."""
