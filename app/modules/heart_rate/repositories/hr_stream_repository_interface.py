"""
HR-stream repository contract.

Backs the existing `hamsatech.athletes` table (for athlete resolution —
same `get_by_contact_number` shape as `OnboardingRepositoryInterface` /
`PsychologyResponseRepositoryInterface`, kept as its own narrow interface
per the Interface Segregation rationale already used throughout this
project) and the existing `hamsatech.hr_stream` table (one row per HR
sample). `create_many` only ever inserts — `hr_stream` rows are
append-only, never updated or deleted by this project.

Deliberately takes primitive `HrSampleRecord` values rather than the
API-layer `HrSampleItem` schema, so the repository (infrastructure layer)
never depends on `app.modules.heart_rate.schemas` (presentation layer) —
the service is what maps one to the other.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.models.hamsatech_athlete import HamsaTechAthlete


@dataclass(frozen=True, slots=True)
class HrSampleRecord:
    """One HR sample, already validated, ready to persist."""

    session_id: UUID
    recorded_at: datetime
    heart_rate: int
    rr_interval: int | None


class HrStreamRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete and writing their HR samples."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def create_many(self, athlete_id: str, samples: Sequence[HrSampleRecord]) -> int:
        """Insert one `hr_stream` row per sample for `athlete_id`. Returns the number inserted."""
