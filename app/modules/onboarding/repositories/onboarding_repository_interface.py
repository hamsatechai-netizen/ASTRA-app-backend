"""
Onboarding-profile repository contract.

Backs the existing `hamsatech.athletes` table (see
`app.models.hamsatech_athlete`), narrowly scoped to what onboarding needs:
resolving the athlete by contact number and saving Step 1's fields. This
is deliberately a separate, narrow interface from
`app.modules.auth.repositories.AthleteProfileRepositoryInterface` (same
table, different consumer, same Interface Segregation rationale already
used throughout this project) — it does not touch or replace that
interface, and never creates a new athlete row.
"""

from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from app.models.hamsatech_athlete import HamsaTechAthlete


class OnboardingRepositoryInterface(ABC):
    """Abstract contract for reading and updating athlete onboarding data."""

    @abstractmethod
    async def get_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def save_step_1(
        self,
        athlete: HamsaTechAthlete,
        *,
        full_name: str,
        date_of_birth: date,
        gender: str,
        city: str,
    ) -> HamsaTechAthlete:
        """
        Persist Step 1 (Personal Details) onto `athlete` and advance
        `current_onboarding_step` to 2. Updates only `athlete_name`,
        `date_of_birth`, `gender`, `city`, and `current_onboarding_step` —
        no other column on `athlete` is touched.
        """

    @abstractmethod
    async def save_step_2(
        self,
        athlete: HamsaTechAthlete,
        *,
        discipline: str,
        experience_level: str,
        years_shooting: int,
        academy_id: UUID,
    ) -> HamsaTechAthlete:
        """
        Persist Step 2 (Athletic Background) onto `athlete` and advance
        `current_onboarding_step` to 3. Updates only
        `weapon_specialization`, `experience_level`, `years_shooting`,
        `academy_id`, and `current_onboarding_step` — no other column on
        `athlete` is touched.
        """

    @abstractmethod
    async def save_step_3(
        self,
        athlete: HamsaTechAthlete,
        *,
        average_practice_score: float,
        target_score: float,
        performance_blockers: list[str],
        goal_30_day: str,
        goal_6_month: str,
    ) -> HamsaTechAthlete:
        """
        Persist Step 3 (Track Your Performance) onto `athlete` and advance
        `current_onboarding_step` to 4. Updates only `avg_practice_score`,
        `target_score`, `performance_blockers`, `goal_30_day`,
        `goal_6_month`, and `current_onboarding_step` — no other column on
        `athlete` is touched.
        """

    @abstractmethod
    async def advance_onboarding_step(self, athlete: HamsaTechAthlete, step: int) -> HamsaTechAthlete:
        """Set `athlete.current_onboarding_step` to `step` — no other column on `athlete` is touched."""
