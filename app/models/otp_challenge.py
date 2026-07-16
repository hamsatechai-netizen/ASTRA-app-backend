"""
OTP challenge persistence model.

One row per phone number: each new send-otp request overwrites
(upserts) the existing row rather than inserting a new one — that
overwrite is what "reset the attempt counter" means in practice, and it
keeps "is there a recent request for this phone" a single indexed lookup.

`otp_hash` is a self-contained Argon2id PHC-format string (see
`app.modules.auth.security.hashing.hash_otp`) that already embeds its own
random salt, so there is no separate `otp_salt` column — one would just
duplicate what Argon2 stores internally.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.base import TimestampMixin, UUIDMixin


class OTPChallenge(Base, UUIDMixin, TimestampMixin):
    """The current OTP challenge (if any) for a given phone number."""

    __tablename__ = "otp_challenges"

    phone_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    otp_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
