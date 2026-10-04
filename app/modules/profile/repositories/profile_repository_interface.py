"""
Profile repository contract.

Backs the existing `hamsatech.athletes` table (see
`app.models.hamsatech_athlete`) — the same table onboarding writes to.
Kept as its own narrow interface (same Interface Segregation rationale
documented in `app.modules.sessions.repositories.session_repository_interface`)
rather than extending `AthleteProfileRepositoryInterface` in the auth
module, whose own docstring explicitly scopes it to resolving/creating a
minimal row for onboarding-status purposes only.
"""

from abc import ABC, abstractmethod

from app.models.hamsatech_athlete import HamsaTechAthlete


class ProfileRepositoryInterface(ABC):
    """Abstract contract for reading and updating an athlete's editable profile fields."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def update_fields(
        self,
        athlete: HamsaTechAthlete,
        *,
        athlete_name: str | None = None,
        weapon_specialization: str | None = None,
        experience_level: str | None = None,
        goal_30_day: str | None = None,
        goal_6_month: str | None = None,
    ) -> HamsaTechAthlete:
        """
        Set only the given (non-`None`) fields on `athlete` and persist.

        `None` means "not sent by the client, leave unchanged" — matches
        the existing Flutter client's partial-update wire behavior (it only
        includes a key in the PUT body when the value is non-null/non-empty).
        There is currently no way to explicitly clear a field via this
        endpoint, matching what the client can actually send today.
        """
