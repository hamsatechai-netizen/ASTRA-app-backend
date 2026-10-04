"""Auth module schemas — re-exported here for a single, stable import path."""

from app.common.responses import ErrorResponse
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.auth.schemas.requests import RefreshTokenRequest, SendOTPRequest, VerifyOTPRequest
from app.modules.auth.schemas.responses import AuthResponse, OTPSentResponse, TokenRefreshResponse

__all__ = [
    "SendOTPRequest",
    "VerifyOTPRequest",
    "RefreshTokenRequest",
    "AuthResponse",
    "OTPSentResponse",
    "TokenRefreshResponse",
    "AuthenticatedIdentity",
    "ErrorResponse",
]
