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
