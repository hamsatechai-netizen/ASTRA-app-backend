"""
ORM mapping onto the existing `hamsatech.hr_stream` table — confirmed via
direct inspection: `id` (bigint, PK, `nextval('hamsatech.hr_stream_id_seq')`),
`session_id` (uuid, nullable, no FK), `athlete_id` (text, nullable, no FK —
same loosely-coupled convention as `hamsatech.psychology_responses`),
`recorded_at` (naive timestamp), `heart_rate` (integer), `rr_interval`
(integer), `created_at` (naive timestamp, `DEFAULT now()`).

Uses `ExternalBase`, not `Base`: this project never creates, alters, or
migrates this table — it pre-exists in the `hamsatech` schema.

`id` is a server-generated sequence primary key and is never set from
Python — same pattern as `HamsaTechPsychologyResponse.id` (SQLAlchemy
omits an unset PK column from the INSERT and reads the generated value
back via RETURNING, rather than sending an explicit NULL, so no
`server_default` metadata is needed here the way it is for `created_at`).

Rows are append-only: this project only ever inserts into `hr_stream`,
never updates or deletes a row once written.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class HrStream(ExternalBase):
    """Partial mapping onto the existing `hamsatech.hr_stream` table — one row per HR sample."""

    __tablename__ = "hr_stream"
    __table_args__ = {"schema": "hamsatech"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    athlete_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rr_interval: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
