"""
Top-level auth orchestration service.

Coordinates `OTPService` (challenge/verification) and `TokenService`
(issuance) into the two auth use cases the API exposes. `send_otp` is
implemented; `verify_otp` remains a signature-only stub, since OTP
verification, athlete lookup/creation, and token issuance are all later
phases.
"""

from app.modules.auth.schemas.responses import AuthResponse, OTPSentResponse
from app.modules.auth.services.otp_service import OTPService
from app.modules.auth.services.token_service import TokenService


class AuthService:
    """Orchestrates OTP verification and token issuance into the auth use cases."""

    def __init__(self, otp_service: OTPService, token_service: TokenService) -> None:
        self._otp_service = otp_service
        self._token_service = token_service

    async def send_otp(self, phone_number: str) -> OTPSentResponse:
        """Send an OTP challenge to `phone_number` and return the success acknowledgement."""
        await self._otp_service.send_otp(phone_number)
        return OTPSentResponse()

    async def verify_otp(self, phone_number: str, otp_code: str) -> AuthResponse:
        """Orchestrate OTP verification, athlete lookup/creation, and token issuance."""
        raise NotImplementedError("Verify-OTP orchestration is implemented in a later phase.")
