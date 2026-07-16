"""
Response DTOs for the phone + OTP authentication flow.

`ErrorResponse` for this module's failure cases is intentionally *not*
redefined here — every error path (auth included) uses the project-wide
envelope from `app.common.responses.ErrorResponse`, re-exported from
`app.modules.auth.schemas` for convenience. Duplicating it here would
fragment the API's error contract into a per-module shape.
"""

from uuid import UUID

from pydantic import Field

from app.modules.auth.constants import TOKEN_TYPE_BEARER
from app.schemas.base import BaseSchema


class AuthResponse(BaseSchema):
    """
    Successful authentication result, issued once OTP verification
    succeeds. The shape is fixed now so the API contract (and Swagger) is
    stable ahead of time — actual token issuance is implemented in Phase 2.
    """

    access_token: str = Field(..., description="Short-lived JWT used to authenticate subsequent requests.")
    refresh_token: str = Field(..., description="Long-lived token used to obtain a new access token.")
    token_type: str = Field(default=TOKEN_TYPE_BEARER, description="RFC 6750 token type.")
    expires_in: int = Field(..., description="Seconds until the access token expires.")
    athlete_id: UUID = Field(..., description="Unique identifier of the authenticated athlete.")
    is_new_athlete: bool = Field(
        ..., description="True if this OTP verification created a new athlete record."
    )


class OTPSentResponse(BaseSchema):
    """Acknowledgement returned by `POST /api/v1/auth/phone/send-otp` on success."""

    success: bool = Field(default=True, description="Whether the OTP was sent successfully.")
    message: str = Field(default="OTP sent successfully.", description="Human-readable result message.")
