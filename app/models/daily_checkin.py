"""
ORM mapping onto `hamsatech.daily_checkins` — a table this project itself
created (`migrations/versions/0005_create_daily_checkins.py`), the same
"reviewed exception" precedent as `hamsatech.session_series`: no existing
table stored a recurring daily subjective-state record (confirmed by a
full audit of every table in `hamsatech` before this migration was
written). Distinct from `hamsatech.session_post_log.mood`, which is a
different, per-session concept.

One row per `(athlete_id, checkin_date)`, enforced by a UNIQUE constraint
at the DB level — `id` is a separate synthetic primary key, matching the
same shape already used by `hamsatech.session_series`. The real table
also carries a foreign key from `athlete_id` to
`hamsatech.athletes(athlete_id)` (safe: both tables share the `hamsatech`
schema) — not restated in this column's mapping, same convention already
used by `hamsatech.session_series.session_id` (the DB enforces it, the
ORM metadata doesn't repeat it).

Uses `ExternalBase`, not `Base`: same convention as every other
`hamsatech.*` model, including the ones this project created — the table
is still part of the shared `hamsatech` schema. Deliberately excluded
from `target_metadata` so Alembic autogenerate can never propose further
changes to it.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import ARRAY, Date, DateTime, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class DailyCheckin(ExternalBase):
    """Mapping onto `hamsatech.daily_checkins` — one row per athlete per UTC calendar day."""

    __tablename__ = "daily_checkins"
    __table_args__ = {"schema": "hamsatech"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    athlete_id: Mapped[str] = mapped_column(Text, nullable=False)
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)
    mood: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    energy_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sleep_band: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
