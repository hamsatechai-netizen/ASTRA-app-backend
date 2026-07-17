"""
Athlete-profile repository contract.

Backs the existing `hamsatech.athletes` table (see
`app.models.hamsatech_athlete`). This backend only ever checks for and
creates a minimal row keyed by `contact_number`, to resolve onboarding
status — it has no visibility into or responsibility for the rest of
that table's 17 columns, which are owned entirely by other systems.
"""

from abc import ABC, abstractmethod

from app.models.hamsatech_athlete import HamsaTechAthlete


class AthleteProfileRepositoryInterface(ABC):
    """Abstract contract for reading and minimally creating athlete profiles."""

    @abstractmethod
    async def get_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def create_minimal(self, phone_number: str) -> HamsaTechAthlete:
        """Create a new athlete profile with `contact_number` set to `phone_number`."""
