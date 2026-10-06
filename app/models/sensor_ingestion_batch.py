"""
ORM mapping onto `hamsatech.sensor_ingestion_batches` — one row per ECG/ACC
upload batch the backend has accepted. Created by migration
`0007_sensor_ingestion_batches`.

This is the idempotency ledger for `POST /api/v2/ecg/samples` and
`POST /api/v2/acc/samples`: a client retrying a batch whose response was
lost resends the same `batch_id`, and the primary key
`(session_id, stream_type, batch_id)` guarantees its samples are inserted
at most once. The marker row is written in the same transaction as the
samples, so it exists if and only if the samples were committed.

Kept as a small supporting table rather than a `batch_id` column on every
`ecg_stream` / `acc_stream` row: one ~100-byte row per batch (a few hundred
per streamed hour) instead of 16 extra bytes on each of hundreds of
thousands of sample rows.

`session_id` is part of the key on purpose: by the time a batch is claimed
the session has already been verified as the authenticated athlete's own,
so one athlete's batch ids can never collide with, or reveal anything
about, another athlete's.

Uses `ExternalBase`, not `Base` — same convention as every other
`hamsatech.*` table this project created (`session_series`,
`daily_checkins`): hand-written migration, excluded from Alembic
autogenerate.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class SensorIngestionBatch(ExternalBase):
    """Mapping onto `hamsatech.sensor_ingestion_batches` — one row per accepted sensor batch."""

    __tablename__ = "sensor_ingestion_batches"
    __table_args__ = {"schema": "hamsatech"}

    session_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    stream_type: Mapped[str] = mapped_column(Text, primary_key=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    athlete_id: Mapped[str] = mapped_column(Text, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("now()")
    )
