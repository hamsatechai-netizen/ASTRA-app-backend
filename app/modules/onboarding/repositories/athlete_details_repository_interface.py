"""
Athlete-details repository contract.

Backs the existing `hamsatech.athlete_details` table (see
`app.models.hamsatech_athlete_details`), narrowly scoped to Onboarding
Step 4 (Academic Profile): `class`, `school_name`, `academic_performance`.
One row per athlete (`athlete_id` is unique on the real table) — `create`
must only ever be called once no such row exists yet.
"""

from abc import ABC, abstractmethod

from app.models.hamsatech_athlete_details import HamsaTechAthleteDetails


class AthleteDetailsRepositoryInterface(ABC):
    """Abstract contract for reading, creating, and updating academic-profile details."""

    @abstractmethod
    async def get_by_athlete_id(self, athlete_id: str) -> HamsaTechAthleteDetails | None:
        """Return the details row for `athlete_id`, or None if it doesn't exist yet."""

    @abstractmethod
    async def create(
        self, athlete_id: str, *, class_: str, school_name: str, academic_performance: str
    ) -> HamsaTechAthleteDetails:
        """Create the (single, unique) details row for `athlete_id`."""

    @abstractmethod
    async def update(
        self,
        details: HamsaTechAthleteDetails,
        *,
        class_: str,
        school_name: str,
        academic_performance: str,
    ) -> HamsaTechAthleteDetails:
        """Update `class_`, `school_name`, and `academic_performance` on an existing `details` row."""
