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

from app.modules.auth.constants import TOKEN_TYPE_BEARER, OnboardingStatus
from app.schemas.base import BaseSchema


class AuthResponse(BaseSchema):
    """Successful authentication result, issued once OTP verification succeeds."""

    access_token: str = Field(..., description="Short-lived JWT used to authenticate subsequent requests.")
    refresh_token: str = Field(..., description="Long-lived token used to obtain a new access token.")
    token_type: str = Field(default=TOKEN_TYPE_BEARER, description="RFC 6750 token type.")
    expires_in: int = Field(..., description="Seconds until the access token expires.")
    # Named `user_id`, not `athlete_id`: this is `hamsatech.users.id` (a UUID),
    # a distinct identifier from `hamsatech.athletes.athlete_id` (a text ID
    # like "ASA051") on a different table entirely. See `next_step` below for
    # how the client learns whether an athlete profile exists yet.
    user_id: UUID = Field(..., description="Unique identifier of the authenticated user.")
    is_new_user: bool = Field(..., description="True if this OTP verification created a new user record.")
    next_step: OnboardingStatus = Field(
        ...,
        description=(
            "Where the client should route to: HOME if onboarding is complete, "
            "otherwise the athlete's saved onboarding step (ONBOARDING_STEP_1 .. ONBOARDING_STEP_6)."
        ),
    )


class OTPSentResponse(BaseSchema):
    """Acknowledgement returned by `POST /api/v2/auth/phone/send-otp` on success."""

    success: bool = Field(default=True, description="Whether the OTP was sent successfully.")
    message: str = Field(default="OTP sent successfully.", description="Human-readable result message.")


class TokenRefreshResponse(BaseSchema):
    """
    Successful result of `POST /api/v2/auth/refresh`.

    Deliberately not `AuthResponse`: a refresh exchanges tokens only, it
    never re-resolves `is_new_user`/`next_step` (that identity/onboarding
    resolution only happens on OTP verification), so reusing that schema
    here would advertise fields this endpoint never actually recomputes.
    """

    access_token: str = Field(..., description="Newly issued short-lived JWT.")
    refresh_token: str = Field(
        ..., description="Newly issued long-lived refresh token — store this in place of the old one."
    )
    token_type: str = Field(default=TOKEN_TYPE_BEARER, description="RFC 6750 token type.")
    expires_in: int = Field(..., description="Seconds until the new access token expires.")
