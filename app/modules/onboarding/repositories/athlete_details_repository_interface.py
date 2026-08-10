"""
Athlete-details repository contract.

Backs the existing `hamsatech.athlete_details` table (see
`app.models.hamsatech_athlete_details`), scoped to Onboarding Step 4
(Academic Profile), Step 5 (Lifestyle & Wellness), and Step 6 (Mental &
Social Profile). One row per athlete (`athlete_id` is unique on the real
table) — each step's `create_*` must only ever be called once no such
row exists yet; `update_*` only ever touches that step's own columns.
"""

from abc import ABC, abstractmethod

from app.models.hamsatech_athlete_details import HamsaTechAthleteDetails


class AthleteDetailsRepositoryInterface(ABC):
    """Abstract contract for reading, creating, and updating athlete-details data."""

    @abstractmethod
    async def get_by_athlete_id(self, athlete_id: str) -> HamsaTechAthleteDetails | None:
        """Return the details row for `athlete_id`, or None if it doesn't exist yet."""

    @abstractmethod
    async def create(
        self, athlete_id: str, *, class_: str, school_name: str, academic_performance: str
    ) -> HamsaTechAthleteDetails:
        """Create the (single, unique) details row for `athlete_id` (Step 4 fields)."""

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

    @abstractmethod
    async def create_step_5(
        self,
        athlete_id: str,
        *,
        diet_type: str,
        outside_food_frequency: str,
        sleep_time: str,
        wake_time: str,
    ) -> HamsaTechAthleteDetails:
        """Create the (single, unique) details row for `athlete_id` (Step 5 fields)."""

    @abstractmethod
    async def update_step_5(
        self,
        details: HamsaTechAthleteDetails,
        *,
        diet_type: str,
        outside_food_frequency: str,
        sleep_time: str,
        wake_time: str,
    ) -> HamsaTechAthleteDetails:
        """Update `diet_type`, `outside_food_frequency`, `sleep_time`, and `wake_time` on `details`."""

    @abstractmethod
    async def create_step_6(
        self,
        athlete_id: str,
        *,
        friend_circle: str,
        anger_pattern: str,
        sadness_pattern: str,
        reason_for_shooting: str,
        athlete_goal: str,
    ) -> HamsaTechAthleteDetails:
        """Create the (single, unique) details row for `athlete_id` (Step 6 fields)."""

    @abstractmethod
    async def update_step_6(
        self,
        details: HamsaTechAthleteDetails,
        *,
        friend_circle: str,
        anger_pattern: str,
        sadness_pattern: str,
        reason_for_shooting: str,
        athlete_goal: str,
    ) -> HamsaTechAthleteDetails:
        """Update `friend_circle`, `anger_pattern`, `sadness_pattern`, `reason_for_shooting`,
        and `athlete_goal` on `details`."""
