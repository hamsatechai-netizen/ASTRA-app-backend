"""
ORM mapping onto the existing `hamsatech.ecg_stream` table — confirmed via
direct inspection (`information_schema`): `id` (bigint, PK,
`nextval('hamsatech.ecg_stream_id_seq')`), `session_id` (uuid, nullable,
no FK), `athlete_id` (text, nullable, no FK), `recorded_at` (naive
timestamp), `ecg_value` (integer), `created_at` (naive timestamp,
`DEFAULT now()`). Same column shape and conventions as `HrStream`.

Uses `ExternalBase`, not `Base`: this project never creates, alters, or
drops this table — it pre-exists in the `hamsatech` schema. (Migration
`0006_add_sensor_stream_indexes` only adds an index to it.)

One row per ECG sample. `ecg_value` is the Polar H10's ECG voltage in
microvolts (µV); `recorded_at` is stored as naive UTC, matching
`hr_stream`. Rows are append-only: this project only ever inserts.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class EcgStream(ExternalBase):
    """Mapping onto the existing `hamsatech.ecg_stream` table — one row per ECG sample."""

    __tablename__ = "ecg_stream"
    __table_args__ = {"schema": "hamsatech"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    athlete_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    ecg_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
