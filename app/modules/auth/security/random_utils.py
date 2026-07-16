"""
Cryptographically secure random generation.

Uses the standard library's `secrets` module (CSPRNG), never `random`,
for anything security-sensitive — OTP codes, opaque tokens, etc.
"""

import secrets
import string


def generate_secure_numeric_code(length: int) -> str:
    """Return a cryptographically secure random string of `length` decimal digits."""
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_secure_token(length: int = 32) -> str:
    """Return a cryptographically secure, URL-safe random token of `length` bytes of entropy."""
    return secrets.token_urlsafe(length)
