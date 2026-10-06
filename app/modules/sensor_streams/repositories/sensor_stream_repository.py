"""
Concrete sensor-stream repository (SQLAlchemy) against the existing
`hamsatech.athletes`, `hamsatech.sessions`, `hamsatech.ecg_stream` and
`hamsatech.acc_stream` tables.

Each batch is written with a single Core `insert()` executed against a
list of parameter sets (an executemany), not one ORM object per row — a
batch can be thousands of samples. Only ever executes, never commits: the
request-scoped `AsyncSession` from `app.dependencies.database.get_db` owns
the transaction boundary, so a whole batch commits together or (on any
error) rolls back together — never a partially written batch.

Idempotency: `claim_batch` writes the batch's marker row into
`hamsatech.sensor_ingestion_batches` in that same transaction, so the
marker is committed if and only if the samples are.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.acc_stream import AccStream
from app.models.ecg_stream import EcgStream
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.sensor_ingestion_batch import SensorIngestionBatch
from app.models.session import Session
from app.modules.sensor_streams.repositories.sensor_stream_repository_interface import (
    AccSampleRecord,
    EcgSampleRecord,
    SensorStreamRepositoryInterface,
)


def _to_naive_utc(value: datetime) -> datetime:
    """Normalize an aware timestamp to naive UTC — the `recorded_at` convention shared with `hr_stream`."""
    return value.astimezone(UTC).replace(tzinfo=None)


class SensorStreamRepository(SensorStreamRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def get_session_by_id(self, session_id: UUID) -> Session | None:
        result = await self._session.execute(select(Session).where(Session.session_id == session_id))
        return result.scalar_one_or_none()

    async def claim_batch(
        self,
        *,
        athlete_id: str,
        session_id: UUID,
        stream_type: str,
        batch_id: UUID,
        accepted_count: int,
    ) -> bool:
        """
        Claim the batch with a single `INSERT ... ON CONFLICT DO NOTHING RETURNING`.

        There is deliberately no prior SELECT: the primary key
        `(session_id, stream_type, batch_id)` decides. If another transaction is inserting
        the same key right now, PostgreSQL makes this statement wait for it — then either
        that transaction committed (this insert does nothing → returns False) or it rolled
        back (this insert proceeds → returns True). So two concurrent duplicates can never
        both claim, and a failed first attempt never blocks a retry.

        The row is part of the caller's transaction: if inserting the samples fails
        afterwards, the request-level rollback removes this marker too.
        """
        statement = (
            pg_insert(SensorIngestionBatch)
            .values(
                session_id=session_id,
                stream_type=stream_type,
                batch_id=batch_id,
                athlete_id=athlete_id,
                accepted_count=accepted_count,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    SensorIngestionBatch.session_id,
                    SensorIngestionBatch.stream_type,
                    SensorIngestionBatch.batch_id,
                ]
            )
            .returning(SensorIngestionBatch.batch_id)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def get_batch_accepted_count(
        self, *, session_id: UUID, stream_type: str, batch_id: UUID
    ) -> int | None:
        result = await self._session.execute(
            select(SensorIngestionBatch.accepted_count).where(
                SensorIngestionBatch.session_id == session_id,
                SensorIngestionBatch.stream_type == stream_type,
                SensorIngestionBatch.batch_id == batch_id,
            )
        )
        return result.scalar_one_or_none()

    async def insert_ecg_samples(
        self, athlete_id: str, session_id: UUID, samples: Sequence[EcgSampleRecord]
    ) -> int:
        rows = [
            {
                "session_id": session_id,
                "athlete_id": athlete_id,
                "recorded_at": _to_naive_utc(sample.recorded_at),
                "ecg_value": sample.ecg_value,
            }
            for sample in samples
        ]
        await self._session.execute(insert(EcgStream), rows)
        return len(rows)

    async def insert_acc_samples(
        self, athlete_id: str, session_id: UUID, samples: Sequence[AccSampleRecord]
    ) -> int:
        rows = [
            {
                "session_id": session_id,
                "athlete_id": athlete_id,
                "recorded_at": _to_naive_utc(sample.recorded_at),
                "acc_x": sample.acc_x,
                "acc_y": sample.acc_y,
                "acc_z": sample.acc_z,
            }
            for sample in samples
        ]
        await self._session.execute(insert(AccStream), rows)
        return len(rows)
