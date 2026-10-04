"""
ORM mapping onto `hamsatech.session_series` — a table this project itself
created (`migrations/versions/0004_create_session_series.py`, the one
deliberate exception to not owning the `hamsatech` schema, made because
no existing table stored per-series data). One row per
`(session_id, series_number)`, enforced by a UNIQUE constraint at the DB
level — `id` is a separate synthetic primary key, matching the same shape
already used by `hamsatech.session_post_log` / `hamsatech.session_pre_log`.

Uses `ExternalBase`, not `Base`: even though this project created the
table, it's still part of the `hamsatech` schema shared with the rest of
that system, not this project's own migrated-and-owned tables — same
convention as every other `hamsatech.*` model. Deliberately excluded from
`target_metadata` so Alembic autogenerate can never propose further
changes to it.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class SessionSeries(ExternalBase):
    """Mapping onto `hamsatech.session_series` — one row per session's completed series."""

    __tablename__ = "session_series"
    __table_args__ = {"schema": "hamsatech"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    series_number: Mapped[int] = mapped_column(Integer, nullable=False)
    total_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    shots_fired: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
