"""Request DTOs for the phone + OTP authentication flow."""

import re

from pydantic import Field, field_validator

from app.modules.auth.constants import OTP_CODE_PATTERN, PHONE_NUMBER_PATTERN
from app.schemas.base import BaseSchema

_PHONE_PUNCTUATION = re.compile(r"[\s\-()]")


class SendOTPRequest(BaseSchema):
    """Request body for `POST /api/v1/auth/phone/send-otp`."""

    phone: str = Field(
        ...,
        pattern=PHONE_NUMBER_PATTERN,
        description="E.164-formatted phone number to send the OTP to.",
        examples=["+919876543210"],
    )

    @field_validator("phone", mode="before")
    @classmethod
    def _normalize_phone(cls, value: object) -> object:
        """Strip whitespace/dashes/parentheses before the E.164 pattern is checked."""
        if isinstance(value, str):
            return _PHONE_PUNCTUATION.sub("", value)
        return value


class VerifyOTPRequest(BaseSchema):
    """Request body for `POST /api/v1/auth/phone/verify-otp`."""

    phone_number: str = Field(
        ...,
        pattern=PHONE_NUMBER_PATTERN,
        description="E.164-formatted phone number the OTP was sent to.",
        examples=["+14155552671"],
    )
    otp_code: str = Field(
        ...,
        pattern=OTP_CODE_PATTERN,
        description="The one-time passcode received via SMS.",
        examples=["123456"],
    )
