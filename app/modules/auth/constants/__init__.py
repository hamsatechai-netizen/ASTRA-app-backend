"""
Auth module constants.

Fixed contract/policy values for the phone+OTP auth flow — not
environment-tunable configuration (that belongs in `app.config.settings`),
just the numbers and patterns the schemas, security utilities, and (in
Phase 2) services are all defined in terms of, kept in one place so they
never drift apart.
"""

from typing import Final

# --- OTP -------------------------------------------------------------------
OTP_LENGTH: Final[int] = 6
OTP_EXPIRY_SECONDS: Final[int] = 300  # 5 minutes
OTP_MAX_VERIFICATION_ATTEMPTS: Final[int] = 5
OTP_RESEND_COOLDOWN_SECONDS: Final[int] = 60

# --- JWT ---------------------------------------------------------------------
JWT_ALGORITHM: Final[str] = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = 15
REFRESH_TOKEN_EXPIRE_DAYS: Final[int] = 30
TOKEN_TYPE_BEARER: Final[str] = "bearer"

# --- Format validation -------------------------------------------------------
# E.164 international phone number format, e.g. +14155552671.
PHONE_NUMBER_PATTERN: Final[str] = r"^\+[1-9]\d{7,14}$"
# Numeric OTP code of exactly OTP_LENGTH digits.
OTP_CODE_PATTERN: Final[str] = rf"^\d{{{OTP_LENGTH}}}$"
