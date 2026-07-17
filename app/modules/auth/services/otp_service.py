"""
OTP business-logic service.

Both Send OTP and Verify OTP are fully implemented: send enforces the
resend cooldown, generates and hashes a new OTP, persists it, then
dispatches it via the configured SMS provider; verify checks the active
challenge's expiry and attempt count, compares the hash, and consumes
(deletes) the challenge on success so it can never be replayed.
"""

from datetime import timedelta

from loguru import logger

from app.modules.auth.constants import (
    OTP_EXPIRY_SECONDS,
    OTP_MAX_VERIFICATION_ATTEMPTS,
    OTP_RESEND_COOLDOWN_SECONDS,
)
from app.modules.auth.exceptions import InvalidOTPException, OTPExpiredException, TooManyAttemptsException
from app.modules.auth.providers.sms_provider import SMSProviderInterface
from app.modules.auth.repositories.otp_repository_interface import OTPRepositoryInterface
from app.modules.auth.security import (
    calculate_otp_expiry,
    generate_otp_code,
    hash_otp,
    is_expired,
    verify_otp_hash,
)


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

    async def verify_otp(self, phone_number: str, otp_code: str) -> None:
        """
        Verify `otp_code` against the active challenge for `phone_number`.

        Raises `InvalidOTPException` if no challenge exists (or the code is
        wrong), `OTPExpiredException` if the challenge has expired, or
        `TooManyAttemptsException` if the attempt limit has been reached.
        On success the challenge is deleted so it can never be replayed.
        """
        challenge = await self._repository.get_by_phone(phone_number)
        if challenge is None:
            raise InvalidOTPException("No OTP was requested for this phone number.")

        if challenge.attempts >= OTP_MAX_VERIFICATION_ATTEMPTS:
            raise TooManyAttemptsException("Too many incorrect attempts. Please request a new OTP.")

        if is_expired(challenge.expires_at):
            raise OTPExpiredException()

        if not verify_otp_hash(otp_code, challenge.otp_hash):
            await self._repository.increment_attempts(phone_number)
            raise InvalidOTPException()

        await self._repository.delete_by_phone(phone_number)
        logger.info("OTP verified successfully for phone {}", phone_number)

    async def _enforce_resend_cooldown(self, phone_number: str) -> None:
        """Reject with `TooManyAttemptsException` if `phone_number` requested an OTP too recently."""
        existing = await self._repository.get_by_phone(phone_number)
        if existing is None:
            return

        cooldown_ends_at = existing.updated_at + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)
        if not is_expired(cooldown_ends_at):
            raise TooManyAttemptsException("Please wait before requesting another OTP.")
