"""
Auth router.

`send_otp` is fully implemented: validates the phone number, then
delegates to `AuthService` (which enforces the resend cooldown, generates
and hashes the OTP, persists it, and dispatches it via SMS). `verify_otp`
remains an undocumented-logic placeholder — always returns HTTP 501 — since
OTP verification is a later phase. Mounted under `/api/v1/auth` via
`app/api/v1/router.py`, giving the full paths
`/api/v1/auth/phone/send-otp` and `/api/v1/auth/phone/verify-otp`.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.auth.dependencies.services import get_auth_service
from app.modules.auth.schemas import (
    AuthResponse,
    ErrorResponse,
    OTPSentResponse,
    SendOTPRequest,
    VerifyOTPRequest,
)
from app.modules.auth.services.auth_service import AuthService

router = APIRouter()

_SEND_OTP_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "The phone number failed E.164 format validation.",
    },
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "model": ErrorResponse,
        "description": "An OTP was already requested for this phone number too recently.",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorResponse,
        "description": "The SMS provider failed to deliver the OTP, or an unexpected error occurred.",
    },
}

_VERIFY_OTP_NOT_IMPLEMENTED_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_501_NOT_IMPLEMENTED: {
        "model": ErrorResponse,
        "description": "Not implemented yet — Verify OTP is a later phase.",
    },
}


@router.post(
    "/phone/send-otp",
    response_model=OTPSentResponse,
    responses=_SEND_OTP_RESPONSES,
    summary="Send a one-time passcode to a phone number",
    description=(
        "Validates the phone number, generates and securely hashes a 6-digit "
        "OTP, persists it with a 10-minute expiry (resetting any prior attempt "
        "counter), and dispatches it via the configured SMS provider. The OTP "
        "itself is never returned in the response or logged."
    ),
    tags=["Authentication"],
)
async def send_otp(
    payload: SendOTPRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> OTPSentResponse:
    """Send a one-time passcode to `payload.phone`."""
    return await auth_service.send_otp(payload.phone)


@router.post(
    "/phone/verify-otp",
    response_model=AuthResponse,
    responses=_VERIFY_OTP_NOT_IMPLEMENTED_RESPONSE,
    summary="Verify a one-time passcode and authenticate",
    description=(
        "Verifies the OTP for the given phone number and, on success, issues "
        "an access/refresh token pair. **Not implemented in this phase — "
        "always returns HTTP 501.**"
    ),
    tags=["Authentication"],
)
async def verify_otp(payload: VerifyOTPRequest) -> AuthResponse:
    """Placeholder endpoint. OTP verification and token issuance are implemented in a later phase."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Verify-OTP is not implemented yet.",
    )
