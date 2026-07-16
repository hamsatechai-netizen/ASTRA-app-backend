"""
OTP repository contract.

Deliberately narrower than `AuthRepositoryInterface` (Interface
Segregation): Send OTP only ever needs to read/write the current OTP
challenge for a phone number, never anything about an athlete account.
`AuthRepositoryInterface` remains reserved, untouched, for the
existing/new-user and athlete-creation concerns of a later phase.
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
