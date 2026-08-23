"""
ORM mapping onto the existing `hamsatech.shooting_session_log` table — a
partial projection, not the full 21-column table. Confirmed via direct
`information_schema` inspection: `session_id` is the primary key (unique,
`DEFAULT gen_random_uuid()` — never relied on here, callers always supply
the real session_id), `athlete_id`/`session_date` are `NOT NULL`, every
other column is nullable. `updated_at` has `DEFAULT now()` but that only
applies on INSERT — callers doing an upsert must set it explicitly on
UPDATE.

Only the columns Score Phase 1 needs are mapped: `session_type`,
`total_shots`, `avg_score`, `best_series_score`. Not mapped (real columns
that exist but are out of scope for this phase): `session_duration_min`,
`session_intensity`, `consistency_index`, `technical_rating`,
`stability_rating`, `focus_rating`, `confidence_rating`, `pressure_level`,
`pre_session_fatigue`, `post_session_fatigue`, `is_competition`,
`athlete_notes`, `coach_notes`.

Uses `ExternalBase`, not `Base`: this project never creates, alters, or
migrates this table (same convention as `Session` / `HrStream`).
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class ShootingSessionLog(ExternalBase):
    """Partial mapping onto the existing `hamsatech.shooting_session_log` table."""

    __tablename__ = "shooting_session_log"
    __table_args__ = {"schema": "hamsatech"}

    session_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    athlete_id: Mapped[str] = mapped_column(Text, nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    session_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_shots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    best_series_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
