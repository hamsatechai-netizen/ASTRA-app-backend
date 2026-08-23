"""
ORM mapping onto the existing `hamsatech.session_post_log` table — a
partial projection, not the full table. Confirmed via direct
`information_schema` inspection: `id` (uuid, PK, `DEFAULT gen_random_uuid()`),
`session_id` (uuid, UNIQUE, FOREIGN KEY -> `hamsatech.sessions.session_id`),
`created_at` (naive timestamp, `DEFAULT now()`), plus `mood` (integer),
`what_worked` (text), `what_didnt` (text) — the three reflection columns
added by `migrations/versions/0003_add_reflection_columns.py`.

Only the reflection-relevant columns are mapped. Not mapped (real columns
that exist but carry different, already-in-use semantics — see the audit
behind this module): `focus_level`, `focus_area`, `session_duration`,
`performance_rating`, `challenges`, `coach_feedback`.

Uses `ExternalBase`, not `Base`: this project never creates or drops this
table — see `app.database.external_base`. `0003_add_reflection_columns`
is the one deliberate, reviewed exception that alters it (same pattern as
`0002_add_onboarding_columns` for `hamsatech.athletes`).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class SessionPostLog(ExternalBase):
    """Partial mapping onto the existing `hamsatech.session_post_log` table."""

    __tablename__ = "session_post_log"
    __table_args__ = {"schema": "hamsatech"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    mood: Mapped[int | None] = mapped_column(Integer, nullable=True)
    what_worked: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_didnt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
