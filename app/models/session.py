"""
ORM mapping onto the existing `hamsatech.sessions` table — one row per
training session. Confirmed via direct inspection (`information_schema`):
`session_id` (uuid, PK, `DEFAULT gen_random_uuid()`), `athlete_id` (text,
not null), `session_type` (text, nullable), `start_time`/`end_time`
(timestamp without time zone), `created_at` (timestamp, `DEFAULT now()`).

Uses `ExternalBase`, not `Base`: this project never creates, alters, or
migrates this table (same convention as `HrStream` / `HamsaTechAthlete`).
Related tables (`session_pre_log`, `session_post_log`, `session_summary`,
`shooting_session_log`) exist but are out of scope for this module.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class Session(ExternalBase):
    """Partial mapping onto the existing `hamsatech.sessions` table."""

    __tablename__ = "sessions"
    __table_args__ = {"schema": "hamsatech"}

    session_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    athlete_id: Mapped[str] = mapped_column(Text, nullable=False)
    session_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    # `server_default` matches the real column's `DEFAULT now()` (confirmed
    # via `information_schema`) so a row that never sets this explicitly
    # gets it from the database instead of SQLAlchemy sending an explicit
    # NULL over it (the same class of bug already fixed for
    # `HamsaTechUser.role`/`created_at` and mirrored by `HrStream.created_at`).
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
