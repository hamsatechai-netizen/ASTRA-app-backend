"""
OTP business-logic service.

Send OTP is fully implemented: enforce the resend cooldown, generate and
hash a new OTP, persist it, then dispatch it via the configured SMS
provider. `verify_otp` remains a signature-only stub — verification is a
later phase.
"""

from datetime import timedelta

from loguru import logger

from app.modules.auth.constants import OTP_EXPIRY_SECONDS, OTP_RESEND_COOLDOWN_SECONDS
from app.modules.auth.exceptions import TooManyAttemptsException
from app.modules.auth.providers.sms_provider import SMSProviderInterface
from app.modules.auth.repositories.otp_repository_interface import OTPRepositoryInterface
from app.modules.auth.security import calculate_otp_expiry, generate_otp_code, hash_otp, is_expired


class OTPService:
    """Coordinates OTP generation, hashing, persistence, and SMS dispatch."""

    def __init__(self, repository: OTPRepositoryInterface, sms_provider: SMSProviderInterface) -> None:
        self._repository = repository
        self._sms_provider = sms_provider

    async def send_otp(self, phone_number: str) -> None:
        """Generate, persist, and send a new OTP challenge to `phone_number`."""
        await self._enforce_resend_cooldown(phone_number)

        otp_code = generate_otp_code()
        otp_hash = hash_otp(otp_code)
        expires_at = calculate_otp_expiry(OTP_EXPIRY_SECONDS)

        logger.info("OTP requested for phone {}", phone_number)
        await self._repository.upsert(phone_number=phone_number, otp_hash=otp_hash, expires_at=expires_at)
        logger.info("OTP stored for phone {}", phone_number)

        # `otp_code` only ever appears in the SMS body below — never in a log call.
        message = f"Your ASTRA verification code is {otp_code}. It expires in 10 minutes."
        await self._sms_provider.send(phone_number, message)
        logger.info("SMS sent successfully to {}", phone_number)

    async def verify_otp(self, phone_number: str, otp_code: str) -> bool:
        """
        Verify `otp_code` against the active challenge for `phone_number`.

        Once implemented, raises `InvalidOTPException`, `OTPExpiredException`,
        or `TooManyAttemptsException` on failure instead of returning False.
        """
        raise NotImplementedError("OTP verification is implemented in a later phase.")

    async def _enforce_resend_cooldown(self, phone_number: str) -> None:
        """Reject with `TooManyAttemptsException` if `phone_number` requested an OTP too recently."""
        existing = await self._repository.get_by_phone(phone_number)
        if existing is None:
            return

        cooldown_ends_at = existing.updated_at + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)
        if not is_expired(cooldown_ends_at):
            raise TooManyAttemptsException("Please wait before requesting another OTP.")
