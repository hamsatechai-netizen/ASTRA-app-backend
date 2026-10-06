"""
ECG/ACC ingestion business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one) and verifies the batch's `session_id`
exists in `hamsatech.sessions` and belongs to that athlete — the same
resolve-athlete / session-exists / session-ownership sequence
`HeartRateService.record_samples` uses. `athlete_id` is never taken from
the request body: it is always the server-resolved athlete, so a caller
can only ever write samples for themselves, into their own session.

Idempotency. Every batch carries a client-generated `batch_id`. After the
ownership check, the batch is *claimed* in the idempotency ledger
(`hamsatech.sensor_ingestion_batches`, key `(session_id, stream_type,
batch_id)`) and only the claiming request inserts samples — both in the
one request transaction, so they commit or roll back together:

- first request      → claim succeeds → samples inserted → `accepted = n`
- repeated batch_id  → claim refused  → nothing inserted → the ORIGINAL
                        accepted count is returned, `duplicate = true`
- failed first try   → rollback removes the claim, so a retry is processed
                        as a first request

Because the claim is keyed by `session_id` and only attempted after the
session is proven to be the caller's, another athlete can neither collide
with nor learn anything about this athlete's batches: for someone else's
session the request is rejected (403) before the ledger is touched.

A repeated `batch_id` whose sample count differs from the recorded one is
not a retry of the same batch — it is rejected (409) rather than silently
dropped or silently double-counted.
"""

from collections.abc import Awaitable, Callable
from uuid import UUID

from app.exceptions import ConflictException
from app.modules.sensor_streams.exceptions import (
    AthleteNotFoundException,
    ForbiddenException,
    SessionNotFoundException,
)
from app.modules.sensor_streams.repositories.sensor_stream_repository_interface import (
    AccSampleRecord,
    EcgSampleRecord,
    SensorStreamRepositoryInterface,
)
from app.modules.sensor_streams.schemas.requests import AccSampleBatchRequest, EcgSampleBatchRequest
from app.modules.sensor_streams.schemas.responses import SensorSampleBatchResponse

STREAM_ECG = "ECG"
STREAM_ACC = "ACC"


class BatchIdReusedException(ConflictException):
    """A `batch_id` already accepted for this session/stream was resent with different contents."""

    error_code = "BATCH_ID_REUSED"
    message = "This batchId was already used for a different batch. Use a new batchId for new samples."


class SensorStreamService:
    """Resolves the authenticated athlete, enforces session ownership, and persists ECG/ACC batches."""

    def __init__(self, repository: SensorStreamRepositoryInterface) -> None:
        self._repository = repository

    async def record_ecg_samples(
        self, phone_number: str, payload: EcgSampleBatchRequest
    ) -> SensorSampleBatchResponse:
        """Insert every ECG sample in `payload` for the athlete matching `phone_number` — at most once."""
        athlete_id = await self._resolve_owned_session(phone_number, payload.session_id, stream=STREAM_ECG)
        samples = [EcgSampleRecord(recorded_at=s.recorded_at, ecg_value=s.ecg_value) for s in payload.samples]
        return await self._record_once(
            athlete_id=athlete_id,
            session_id=payload.session_id,
            stream_type=STREAM_ECG,
            batch_id=payload.batch_id,
            sample_count=len(samples),
            insert=lambda: self._repository.insert_ecg_samples(athlete_id, payload.session_id, samples),
        )

    async def record_acc_samples(
        self, phone_number: str, payload: AccSampleBatchRequest
    ) -> SensorSampleBatchResponse:
        """Insert every accelerometer sample in `payload` for the athlete — at most once."""
        athlete_id = await self._resolve_owned_session(phone_number, payload.session_id, stream=STREAM_ACC)
        samples = [
            AccSampleRecord(recorded_at=s.recorded_at, acc_x=s.acc_x, acc_y=s.acc_y, acc_z=s.acc_z)
            for s in payload.samples
        ]
        return await self._record_once(
            athlete_id=athlete_id,
            session_id=payload.session_id,
            stream_type=STREAM_ACC,
            batch_id=payload.batch_id,
            sample_count=len(samples),
            insert=lambda: self._repository.insert_acc_samples(athlete_id, payload.session_id, samples),
        )

    async def _record_once(
        self,
        *,
        athlete_id: str,
        session_id: UUID,
        stream_type: str,
        batch_id: UUID,
        sample_count: int,
        insert: Callable[[], Awaitable[int]],
    ) -> SensorSampleBatchResponse:
        """Claim the batch and insert its samples, or report the already-accepted batch."""
        claimed = await self._repository.claim_batch(
            athlete_id=athlete_id,
            session_id=session_id,
            stream_type=stream_type,
            batch_id=batch_id,
            accepted_count=sample_count,
        )
        if claimed:
            accepted = await insert()
            return SensorSampleBatchResponse(accepted=accepted, duplicate=False)

        recorded = await self._repository.get_batch_accepted_count(
            session_id=session_id, stream_type=stream_type, batch_id=batch_id
        )
        if recorded is None or recorded != sample_count:
            raise BatchIdReusedException()
        return SensorSampleBatchResponse(accepted=recorded, duplicate=True)

    async def _resolve_owned_session(self, phone_number: str, session_id: UUID, *, stream: str) -> str:
        """Return the caller's `athlete_id`, after verifying `session_id` exists and belongs to them."""
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()

        session = await self._repository.get_session_by_id(session_id)
        if session is None:
            raise SessionNotFoundException()
        if session.athlete_id != athlete.athlete_id:
            raise ForbiddenException(f"You may only upload {stream} samples for your own session.")
        return athlete.athlete_id
