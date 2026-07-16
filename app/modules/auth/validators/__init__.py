"""
Reusable format validators for the auth module.

These are standalone functions, not wired into the request schemas via
`AfterValidator` — the schemas already enforce format at the OpenAPI level
via `Field(pattern=...)` (so Swagger shows the constraint), and adding an
`AfterValidator` running the same regex again would just re-check the same
thing twice. These functions exist for the cases *outside* a Pydantic
model — e.g. a Phase-2 service method that receives a raw phone number
string from a token claim or an upstream call, not through
`SendOTPRequest`/`VerifyOTPRequest` — while still sourcing the pattern
from the single definition in `app.modules.auth.constants`.
"""

import re

from app.modules.auth.constants import OTP_CODE_PATTERN, OTP_LENGTH, PHONE_NUMBER_PATTERN


def validate_phone_number(value: str) -> str:
    """Return `value` if it is a valid E.164 phone number, else raise `ValueError`."""
    if not re.fullmatch(PHONE_NUMBER_PATTERN, value):
        raise ValueError("Phone number must be in E.164 format, e.g. +14155552671.")
    return value


def validate_otp_code(value: str) -> str:
    """Return `value` if it is a valid `OTP_LENGTH`-digit numeric code, else raise `ValueError`."""
    if not re.fullmatch(OTP_CODE_PATTERN, value):
        raise ValueError(f"OTP code must be exactly {OTP_LENGTH} numeric digits.")
    return value
