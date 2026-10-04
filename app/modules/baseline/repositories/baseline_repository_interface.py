"""
Baseline repository contract.

Backs the existing `hamsatech.athletes` table (for athlete resolution —
same `get_athlete_by_contact_number` shape as every sibling module's
repository) and the existing, externally-owned `hamsatech.athlete_physiology`
table. No new table, column, or persistence mechanism — see
`app.models.athlete_physiology`.

`athlete_physiology` carries no unique constraint on `athlete_id`, so a
new capture is always an insert, never an upsert — every historical
baseline is preserved.
"""

from abc import ABC, abstractmethod
from datetime import date

from app.models.athlete_physiology import AthletePhysiology
from app.models.hamsatech_athlete import HamsaTechAthlete


class BaselineRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete and creating/reading their baseline."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def create_baseline(
        self, *, athlete_id: str, resting_heart_rate: int, recorded_date: date
    ) -> AthletePhysiology:
        """Insert a new `athlete_physiology` row for `athlete_id`. Always an insert, never an update."""

    @abstractmethod
    async def get_latest_baseline(self, athlete_id: str) -> AthletePhysiology | None:
        """Return `athlete_id`'s most recently created `athlete_physiology` row, if any."""
