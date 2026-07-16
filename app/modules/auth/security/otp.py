"""
OTP generation/expiry utilities.

Pure infrastructure: generating a code and computing when it expires.
Deliberately does not send, store, or verify anything — that's the
persistence/business logic `OTPService` (see `services/otp_service.py`)
will own in Phase 2.
"""

from datetime import datetime

from app.modules.auth.constants import OTP_EXPIRY_SECONDS, OTP_LENGTH
from app.modules.auth.security.expiry import utc_expiry
from app.modules.auth.security.random_utils import generate_secure_numeric_code


def generate_otp_code(length: int = OTP_LENGTH) -> str:
    """Return a new cryptographically secure numeric OTP code."""
    return generate_secure_numeric_code(length)


def calculate_otp_expiry(ttl_seconds: int = OTP_EXPIRY_SECONDS) -> datetime:
    """Return the UTC instant an OTP issued now would expire at."""
    return utc_expiry(ttl_seconds)
