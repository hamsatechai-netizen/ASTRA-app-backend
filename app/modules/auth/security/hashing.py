"""
Secret hashing utilities.

An OTP code is a low-entropy secret (only ~1,000,000 possible 6-digit
values), so a fast hash (SHA-256, etc.) would be brute-forceable in
milliseconds if a hash ever leaked. Argon2id is a deliberately slow,
memory-hard KDF designed for exactly this class of secret. Each call to
`hash_otp` generates its own random salt internally and embeds it in the
returned PHC-format string — there is no separate salt to manage or store.
"""

from argon2 import PasswordHasher

_hasher = PasswordHasher()


def hash_otp(otp_code: str) -> str:
    """Return a salted Argon2id hash of `otp_code`, safe to store at rest."""
    return _hasher.hash(otp_code)
