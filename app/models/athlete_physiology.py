"""
ORM mapping onto the existing, externally-owned `hamsatech.athlete_physiology`
table — a partial projection, not the full column set. The real table also
carries `avg_heart_rate`, `spo2`, `breathing_rate`, `sleep_hours`,
`recovery_score`, `stress_score`, `fatigue_level`, `remarks`, and
`updated_by`, none of which the Baseline module reads or writes today;
they are omitted here rather than mapped-but-unused, following the same
"partial projection" convention as `HamsaTechAthlete`.

Confirmed via live read-only introspection (Baseline Audit) before this
mapping was written: `physiology_id` is the primary key (`uuid`, DB
default `gen_random_uuid()`); `athlete_id` and `session_id` are `text`,
both nullable at the DB level (no NOT NULL, no UNIQUE) — this project
never relies on either being non-null except by always supplying
`athlete_id` itself when creating a row. `athlete_id` carries a FK to
`hamsatech.users(uid)`, not `hamsatech.athletes(athlete_id)` — a
different FK target than `hamsatech.daily_checkins`, but verified safe: a
live join confirmed every existing `athlete_physiology.athlete_id` value
already equals both `hamsatech.athletes.athlete_id` and
`hamsatech.users.uid` (the same identifier space), so writing
`HamsaTechAthlete.athlete_id` here satisfies the real FK. Not restated in
this column's mapping — the DB enforces it, the ORM metadata doesn't
repeat it, same convention as `hamsatech.session_series.session_id`.

Uses `ExternalBase`, not `Base`: this table is not created or migrated by
this project. Deliberately excluded from `target_metadata` so Alembic
autogenerate can never propose changes to it.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class AthletePhysiology(ExternalBase):
    """Partial mapping onto the existing `hamsatech.athlete_physiology` table."""

    __tablename__ = "athlete_physiology"
    __table_args__ = {"schema": "hamsatech"}

    physiology_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    athlete_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resting_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
    last_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
