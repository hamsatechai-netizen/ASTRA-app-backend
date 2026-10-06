"""
Sensor-stream (ECG/ACC) repository contract.

Backs the existing `hamsatech.athletes` / `hamsatech.sessions` tables (for
athlete resolution and session ownership — the same narrow
`get_athlete_by_contact_number` / `get_session_by_id` shape as
`HrStreamRepositoryInterface`, kept per-module per the Interface
Segregation rationale used throughout this project) and the existing
`hamsatech.ecg_stream` / `hamsatech.acc_stream` tables (one row per
sample). The insert methods only ever insert — rows are append-only.

Also backs `hamsatech.sensor_ingestion_batches`, the idempotency ledger:
`claim_batch` must be called (and return True) before a batch's samples are
inserted, in the same transaction.

Takes primitive `*SampleRecord` values rather than the API-layer schemas,
so the repository (infrastructure layer) never depends on
`app.modules.sensor_streams.schemas` (presentation layer).
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session


@dataclass(frozen=True, slots=True)
class EcgSampleRecord:
    """One ECG sample, already validated, ready to persist. `recorded_at` is timezone-aware."""

    recorded_at: datetime
    ecg_value: int


@dataclass(frozen=True, slots=True)
class AccSampleRecord:
    """One accelerometer sample, already validated, ready to persist. `recorded_at` is timezone-aware."""

    recorded_at: datetime
    acc_x: int
    acc_y: int
    acc_z: int


class SensorStreamRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete/session and bulk-writing their ECG/ACC samples."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def get_session_by_id(self, session_id: UUID) -> Session | None:
        """Return the `hamsatech.sessions` row with `session_id`, if any."""

    @abstractmethod
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
        Atomically record that this batch is being accepted, in the current transaction.

        Returns True if this call claimed the batch (the caller must now insert its samples
        in the same transaction), or False if a batch with the same
        `(session_id, stream_type, batch_id)` has already been committed. The database's
        unique constraint is the arbiter — implementations must not check-then-insert.
        """

    @abstractmethod
    async def get_batch_accepted_count(
        self, *, session_id: UUID, stream_type: str, batch_id: UUID
    ) -> int | None:
        """Return the accepted count recorded for an already-committed batch, if any."""

    @abstractmethod
    async def insert_ecg_samples(
        self, athlete_id: str, session_id: UUID, samples: Sequence[EcgSampleRecord]
    ) -> int:
        """Bulk-insert one `ecg_stream` row per sample. Returns the number inserted."""

    @abstractmethod
    async def insert_acc_samples(
        self, athlete_id: str, session_id: UUID, samples: Sequence[AccSampleRecord]
    ) -> int:
        """Bulk-insert one `acc_stream` row per sample. Returns the number inserted."""
