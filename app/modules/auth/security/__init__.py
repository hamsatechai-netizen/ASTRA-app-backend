"""Auth security infrastructure: JWT, secure randomness, OTP math, expiry, and OTP hashing."""

from app.modules.auth.security.expiry import is_expired, utc_expiry
from app.modules.auth.security.hashing import hash_otp, verify_otp_hash
from app.modules.auth.security.jwt import create_access_token, create_refresh_token, decode_token
from app.modules.auth.security.otp import calculate_otp_expiry, generate_otp_code
from app.modules.auth.security.random_utils import generate_secure_numeric_code, generate_secure_token

__all__ = [
    "utc_expiry",
    "is_expired",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "generate_otp_code",
    "calculate_otp_expiry",
    "generate_secure_numeric_code",
    "generate_secure_token",
    "hash_otp",
    "verify_otp_hash",
]
