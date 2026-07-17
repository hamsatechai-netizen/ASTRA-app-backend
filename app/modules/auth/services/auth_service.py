"""
Top-level auth orchestration service.

Coordinates `OTPService` (challenge/verification), `UserService`
(identity + onboarding-status resolution), and `TokenService` (issuance)
into the two auth use cases the API exposes.
"""

from app.modules.auth.schemas.responses import AuthResponse, OTPSentResponse
from app.modules.auth.services.otp_service import OTPService
from app.modules.auth.services.token_service import TokenService
from app.modules.auth.services.user_service import UserService


class AuthService:
    """Orchestrates OTP verification, identity resolution, and token issuance into the auth use cases."""

    def __init__(
        self, otp_service: OTPService, user_service: UserService, token_service: TokenService
    ) -> None:
        self._otp_service = otp_service
        self._user_service = user_service
        self._token_service = token_service

    async def send_otp(self, phone_number: str) -> OTPSentResponse:
        """Send an OTP challenge to `phone_number` and return the success acknowledgement."""
        await self._otp_service.send_otp(phone_number)
        return OTPSentResponse()

    async def verify_otp(self, phone_number: str, otp_code: str) -> AuthResponse:
        """
        Verify `otp_code`, resolve (or create) the user identity and
        athlete-profile onboarding status, and issue a token pair.

        Raises `InvalidOTPException`, `OTPExpiredException`, or
        `TooManyAttemptsException` if verification fails — nothing below
        that point runs, so no user/athlete record is touched for a wrong
        or expired code.
        """
        await self._otp_service.verify_otp(phone_number, otp_code)

        user, is_new_user = await self._user_service.get_or_create_user(phone_number)
        next_step = await self._user_service.resolve_onboarding_status(phone_number)
        tokens = await self._token_service.issue_tokens(user.id)

        return AuthResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in,
            user_id=user.id,
            is_new_user=is_new_user,
            next_step=next_step,
        )
