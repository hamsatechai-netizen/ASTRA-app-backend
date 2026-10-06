"""
Real-PostgreSQL tests for ECG/ACC batch idempotency.

The unit suite proves the service logic against an in-memory ledger; these
prove the part only a real database can: that
`INSERT ... ON CONFLICT DO NOTHING RETURNING` on
`hamsatech.sensor_ingestion_batches` really is atomic under concurrency —
a duplicate arriving while the first request's transaction is still open
WAITS for it, then inserts nothing if it committed, or takes over if it
rolled back — and that the marker and the samples commit or roll back
together.

Runs ONLY when `ASTRA_INTEGRATION_DB_URL` is set, points at a *local*
database (127.0.0.1 / localhost) and equals `DATABASE_URL`; otherwise the
whole module is skipped (same guard as the other integration tests). It can
never target a remote host. It creates the `hamsatech` schema objects it
needs with `IF NOT EXISTS` — the ledger table from migration 0007's own DDL
— and deletes every row it writes.

    DATABASE_URL=postgresql+asyncpg://astra_smoke@127.0.0.1:55432/astra_smoke \\
    ASTRA_INTEGRATION_DB_URL=$DATABASE_URL DATABASE_SSL_REQUIRED=false \\
    pytest tests/integration/test_sensor_idempotency_postgres.py
"""

import asyncio
import importlib.util
import os
import re
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.modules.sensor_streams.repositories.sensor_stream_repository import SensorStreamRepository
from app.modules.sensor_streams.repositories.sensor_stream_repository_interface import (
    AccSampleRecord,
    EcgSampleRecord,
)
from app.modules.sensor_streams.schemas import AccSampleBatchRequest, EcgSampleBatchRequest
from app.modules.sensor_streams.services.sensor_stream_service import (
    BatchIdReusedException,
    SensorStreamService,
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

INTEGRATION_URL = os.environ.get("ASTRA_INTEGRATION_DB_URL", "")
_LOCAL_URL = re.compile(r"^postgresql\+asyncpg://[^@/]+@(127\.0\.0\.1|localhost):\d+/\w+$")

pytestmark = pytest.mark.skipif(
    not _LOCAL_URL.match(INTEGRATION_URL) or os.environ.get("DATABASE_URL") != INTEGRATION_URL,
    reason="requires ASTRA_INTEGRATION_DB_URL pointing at a LOCAL database and equal to DATABASE_URL",
)

ATHLETE_ID = "IT-SENSOR-ATHLETE"
PHONE = "+910000000001"

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "migrations" / "versions" / "0007_sensor_ingestion_batches.py"
)


def _migration() -> Any:
    spec = importlib.util.spec_from_file_location("migration_0007", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Minimal local copies of the externally-owned stream tables (same columns as production).
_STREAM_TABLES = (
    "CREATE SCHEMA IF NOT EXISTS hamsatech",
    """CREATE TABLE IF NOT EXISTS hamsatech.ecg_stream (
        id BIGSERIAL PRIMARY KEY, session_id UUID, athlete_id TEXT,
        recorded_at TIMESTAMP, ecg_value INTEGER, created_at TIMESTAMP DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS hamsatech.acc_stream (
        id BIGSERIAL PRIMARY KEY, session_id UUID, athlete_id TEXT, recorded_at TIMESTAMP,
        acc_x INTEGER, acc_y INTEGER, acc_z INTEGER, created_at TIMESTAMP DEFAULT now())""",
)


class _OwnedSessionRepository(SensorStreamRepository):
    """The real repository for the ledger and sample tables; athlete/session lookups are stubbed
    (those tables are not what is under test here)."""

    def __init__(self, session: AsyncSession, owned_session_ids: set[uuid.UUID]) -> None:
        super().__init__(session)
        self._owned = owned_session_ids

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=phone_number)

    async def get_session_by_id(self, session_id: uuid.UUID) -> Session | None:
        if session_id not in self._owned:
            return None
        return Session(session_id=session_id, athlete_id=ATHLETE_ID, start_time=datetime(2026, 1, 1))


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(INTEGRATION_URL)
    async with engine.begin() as connection:
        for statement in _STREAM_TABLES:
            await connection.execute(text(statement))
        await connection.execute(text(_migration().CREATE_TABLE))
    yield engine
    async with engine.begin() as connection:
        for table in ("ecg_stream", "acc_stream", "sensor_ingestion_batches"):
            await connection.execute(
                text(f"DELETE FROM hamsatech.{table} WHERE athlete_id = :athlete"), {"athlete": ATHLETE_ID}
            )
    await engine.dispose()


@pytest.fixture
def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, expire_on_commit=False)


async def _count(sessions: async_sessionmaker[AsyncSession], table: str, session_id: uuid.UUID) -> int:
    async with sessions() as db:
        result = await db.execute(
            text(f"SELECT count(*) FROM hamsatech.{table} WHERE session_id = :sid"), {"sid": session_id}
        )
        return int(result.scalar_one())


def _ecg_payload(session_id: uuid.UUID, batch_id: uuid.UUID, count: int) -> EcgSampleBatchRequest:
    start = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
    return EcgSampleBatchRequest(
        session_id=session_id,
        batch_id=batch_id,
        samples=[
            {"recorded_at": start + timedelta(milliseconds=8 * i), "ecg_value": i} for i in range(count)
        ],  # type: ignore[list-item]
    )


def _acc_payload(session_id: uuid.UUID, batch_id: uuid.UUID, count: int) -> AccSampleBatchRequest:
    start = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
    return AccSampleBatchRequest(
        session_id=session_id,
        batch_id=batch_id,
        samples=[
            {"recorded_at": start + timedelta(milliseconds=20 * i), "acc_x": i, "acc_y": -i, "acc_z": 1000}
            for i in range(count)
        ],  # type: ignore[list-item]
    )


async def _request(
    sessions: async_sessionmaker[AsyncSession], payload: Any, owned: set[uuid.UUID], *, fail: bool = False
) -> Any:
    """One HTTP-request-equivalent: its own session, commit on success, rollback on error (as `get_db`)."""
    async with sessions() as db:
        try:
            service = SensorStreamService(_OwnedSessionRepository(db, owned))
            if isinstance(payload, EcgSampleBatchRequest):
                response = await service.record_ecg_samples(PHONE, payload)
            else:
                response = await service.record_acc_samples(PHONE, payload)
            if fail:
                raise RuntimeError("simulated failure after the samples were written, before commit")
            await db.commit()
            return response
        except Exception:
            await db.rollback()
            raise


async def test_duplicate_batch_is_stored_once_and_returns_the_original_count(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    session_id, batch_id = uuid.uuid4(), uuid.uuid4()
    payload = _ecg_payload(session_id, batch_id, 130)

    first = await _request(sessions, payload, {session_id})
    retry = await _request(sessions, payload, {session_id})

    assert (first.accepted, first.duplicate) == (130, False)
    assert (retry.accepted, retry.duplicate) == (130, True)
    assert await _count(sessions, "ecg_stream", session_id) == 130
    assert await _count(sessions, "sensor_ingestion_batches", session_id) == 1


async def test_concurrent_duplicate_requests_insert_the_batch_exactly_once(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    session_id, batch_id = uuid.uuid4(), uuid.uuid4()
    payload = _acc_payload(session_id, batch_id, 50)

    results = await asyncio.gather(*(_request(sessions, payload, {session_id}) for _ in range(8)))

    assert sorted(r.duplicate for r in results) == [False] + [True] * 7
    assert {r.accepted for r in results} == {50}
    assert await _count(sessions, "acc_stream", session_id) == 50
    assert await _count(sessions, "sensor_ingestion_batches", session_id) == 1


async def test_duplicate_waits_for_the_open_transaction_then_does_nothing_when_it_commits(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    session_id, batch_id = uuid.uuid4(), uuid.uuid4()
    claim = {
        "athlete_id": ATHLETE_ID,
        "session_id": session_id,
        "stream_type": "ECG",
        "batch_id": batch_id,
        "accepted_count": 3,
    }

    async with sessions() as first, sessions() as second:
        assert await SensorStreamRepository(first).claim_batch(**claim) is True  # uncommitted

        racing = asyncio.create_task(SensorStreamRepository(second).claim_batch(**claim))
        await asyncio.sleep(0.4)
        assert not racing.done()  # blocked on the first transaction — not a race, a queue

        await first.commit()
        assert await asyncio.wait_for(racing, timeout=5) is False
        await second.rollback()


async def test_duplicate_takes_over_when_the_open_transaction_rolls_back(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    session_id, batch_id = uuid.uuid4(), uuid.uuid4()
    claim = {
        "athlete_id": ATHLETE_ID,
        "session_id": session_id,
        "stream_type": "ACC",
        "batch_id": batch_id,
        "accepted_count": 3,
    }

    async with sessions() as first, sessions() as second:
        assert await SensorStreamRepository(first).claim_batch(**claim) is True

        racing = asyncio.create_task(SensorStreamRepository(second).claim_batch(**claim))
        await asyncio.sleep(0.4)
        assert not racing.done()

        await first.rollback()  # the first attempt failed
        assert await asyncio.wait_for(racing, timeout=5) is True  # so the retry is the one that counts
        await second.commit()

    assert await _count(sessions, "sensor_ingestion_batches", session_id) == 1


async def test_failure_before_commit_leaves_no_marker_and_no_samples_and_a_retry_succeeds(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    session_id, batch_id = uuid.uuid4(), uuid.uuid4()
    payload = _ecg_payload(session_id, batch_id, 40)

    with pytest.raises(RuntimeError):
        await _request(sessions, payload, {session_id}, fail=True)

    assert await _count(sessions, "sensor_ingestion_batches", session_id) == 0
    assert await _count(sessions, "ecg_stream", session_id) == 0

    retry = await _request(sessions, payload, {session_id})

    assert (retry.accepted, retry.duplicate) == (40, False)
    assert await _count(sessions, "ecg_stream", session_id) == 40


async def test_same_uuid_for_ecg_and_acc_are_independent_batches(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    session_id, shared = uuid.uuid4(), uuid.uuid4()

    ecg = await _request(sessions, _ecg_payload(session_id, shared, 10), {session_id})
    acc = await _request(sessions, _acc_payload(session_id, shared, 12), {session_id})

    assert (ecg.duplicate, acc.duplicate) == (False, False)
    assert await _count(sessions, "ecg_stream", session_id) == 10
    assert await _count(sessions, "acc_stream", session_id) == 12
    assert await _count(sessions, "sensor_ingestion_batches", session_id) == 2


async def test_same_batch_id_in_two_sessions_are_independent_batches(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    session_a, session_b, shared = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    owned = {session_a, session_b}

    first = await _request(sessions, _ecg_payload(session_a, shared, 5), owned)
    second = await _request(sessions, _ecg_payload(session_b, shared, 7), owned)

    assert (first.duplicate, second.duplicate) == (False, False)
    assert await _count(sessions, "ecg_stream", session_a) == 5
    assert await _count(sessions, "ecg_stream", session_b) == 7


async def test_batch_id_reused_with_different_contents_is_refused_without_writing(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    session_id, batch_id = uuid.uuid4(), uuid.uuid4()
    await _request(sessions, _ecg_payload(session_id, batch_id, 5), {session_id})

    with pytest.raises(BatchIdReusedException):
        await _request(sessions, _ecg_payload(session_id, batch_id, 9), {session_id})

    assert await _count(sessions, "ecg_stream", session_id) == 5


async def test_database_rejects_an_unknown_stream_type(sessions: async_sessionmaker[AsyncSession]) -> None:
    async with sessions() as db:
        with pytest.raises(IntegrityError):
            await SensorStreamRepository(db).claim_batch(
                athlete_id=ATHLETE_ID,
                session_id=uuid.uuid4(),
                stream_type="HR",
                batch_id=uuid.uuid4(),
                accepted_count=1,
            )
        await db.rollback()


async def test_bulk_insert_writes_every_sample(sessions: async_sessionmaker[AsyncSession]) -> None:
    session_id = uuid.uuid4()
    start = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
    async with sessions() as db:
        repository = SensorStreamRepository(db)
        ecg = [
            EcgSampleRecord(recorded_at=start + timedelta(milliseconds=8 * i), ecg_value=i)
            for i in range(2000)
        ]
        acc = [
            AccSampleRecord(recorded_at=start + timedelta(milliseconds=20 * i), acc_x=i, acc_y=-i, acc_z=1000)
            for i in range(2000)
        ]
        assert await repository.insert_ecg_samples(ATHLETE_ID, session_id, ecg) == 2000
        assert await repository.insert_acc_samples(ATHLETE_ID, session_id, acc) == 2000
        await db.commit()

    assert await _count(sessions, "ecg_stream", session_id) == 2000
    assert await _count(sessions, "acc_stream", session_id) == 2000
