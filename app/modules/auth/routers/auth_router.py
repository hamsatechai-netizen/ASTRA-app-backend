"""
Auth router.

All three endpoints delegate entirely to `AuthService`: `send_otp`
enforces the resend cooldown, generates and hashes the OTP, persists it,
and dispatches it via SMS; `verify_otp` verifies the code, resolves (or
creates) the user identity and athlete onboarding status, and issues a
token pair; `refresh` exchanges a valid refresh token for a new pair,
without re-running OTP verification. Mounted under `/api/v2/auth` via
`app/api/v2/router.py`, giving the full paths `/api/v2/auth/phone/send-otp`,
`/api/v2/auth/phone/verify-otp`, and `/api/v2/auth/refresh`.
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.services import get_auth_service
from app.modules.auth.schemas import (
    AuthResponse,
    ErrorResponse,
    OTPSentResponse,
    RefreshTokenRequest,
    SendOTPRequest,
    TokenRefreshResponse,
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

_REFRESH_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": (
            "The refresh token is malformed, has an invalid signature, is an access token "
            "presented as a refresh token (INVALID_TOKEN), or is a well-formed refresh token "
            "past its 30-day expiry (TOKEN_EXPIRED) — either way, the client must send the "
            "user through OTP login again."
        ),
    },
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "The request body is missing `refresh_token`.",
    },
}

_VERIFY_OTP_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "model": ErrorResponse,
        "description": "The OTP is invalid or has expired.",
    },
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": (
            "Identity mapping conflict: for a brand-new athlete, the account's existing uid "
            "disagrees with the generated athlete_id (IDENTITY_CONFLICT), or that athlete_id is "
            "already linked to another account (UID_ALREADY_ASSIGNED); or, for any login, the "
            "phone number matches more than one athlete profile (AMBIGUOUS_ATHLETE_MATCH). "
            "Nothing is persisted."
        ),
    },
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "The phone number or OTP code failed format validation.",
    },
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "model": ErrorResponse,
        "description": "Too many incorrect attempts for this phone number's active OTP.",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorResponse,
        "description": "An unexpected error occurred.",
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
    responses=_VERIFY_OTP_RESPONSES,
    summary="Verify a one-time passcode and authenticate",
    description=(
        "Verifies the OTP for the given phone number. On success, resolves "
        "(or creates) the user identity and athlete onboarding status, and "
        "issues an access/refresh token pair."
    ),
    tags=["Authentication"],
)
async def verify_otp(
    payload: VerifyOTPRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    """Verify `payload.otp_code` for `payload.phone_number` and authenticate."""
    return await auth_service.verify_otp(payload.phone_number, payload.otp_code)


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    responses=_REFRESH_RESPONSES,
    summary="Exchange a refresh token for a new access token",
    description=(
        "Validates the given refresh token and issues a new access/refresh token pair. "
        "The request and response are never logged with their token contents — only the "
        "generic error code on failure."
    ),
    tags=["Authentication"],
)
async def refresh(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenRefreshResponse:
    """Exchange `payload.refresh_token` for a new access/refresh token pair."""
    return await auth_service.refresh_tokens(payload.refresh_token)
