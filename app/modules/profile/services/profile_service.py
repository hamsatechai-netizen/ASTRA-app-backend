"""
Profile business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition `SessionService` and
`HeartRateService` rely on), enforces that the caller can only read/update
their own `athlete_id` (part of the URL, like every other `/api/mobile`
endpoint), and applies only the fields the client actually sent.
"""

from datetime import date

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.profile.exceptions import AthleteNotFoundException, ForbiddenException
from app.modules.profile.repositories.profile_repository_interface import ProfileRepositoryInterface
from app.modules.profile.schemas.requests import UpdateProfileRequest
from app.modules.profile.schemas.responses import ProfileResponse
from app.utils.datetime import utc_now


class ProfileService:
    """Resolves the authenticated athlete and reads/updates their editable profile fields."""

    def __init__(self, repository: ProfileRepositoryInterface) -> None:
        self._repository = repository

    async def get_profile(self, phone_number: str, athlete_id: str) -> ProfileResponse:
        athlete = await self._get_owned_athlete_or_raise(phone_number, athlete_id)
        return _to_response(athlete)

    async def update_profile(
        self, phone_number: str, athlete_id: str, payload: UpdateProfileRequest
    ) -> ProfileResponse:
        athlete = await self._get_owned_athlete_or_raise(phone_number, athlete_id)

        athlete = await self._repository.update_fields(
            athlete,
            athlete_name=payload.full_name,
            weapon_specialization=payload.discipline,
            experience_level=payload.experience_level,
            goal_30_day=payload.goal_30_day,
            goal_6_month=payload.goal_6_month,
        )

        return _to_response(athlete)

    async def _get_owned_athlete_or_raise(self, phone_number: str, athlete_id: str) -> HamsaTechAthlete:
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        if athlete.athlete_id != athlete_id:
            raise ForbiddenException("You may only access your own athlete profile.")
        return athlete


def _compute_age(date_of_birth: date | None) -> int | None:
    """Whole years between `date_of_birth` and today (UTC), or `None` if unset."""
    if date_of_birth is None:
        return None
    today = utc_now().date()
    age = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age


def _to_response(athlete: HamsaTechAthlete) -> ProfileResponse:
    return ProfileResponse(
        athlete_id=athlete.athlete_id,
        athlete_name=athlete.athlete_name,
        date_of_birth=athlete.date_of_birth,
        age=_compute_age(athlete.date_of_birth),
        gender=athlete.gender,
        sport_domain=athlete.weapon_specialization,
        experience_level=athlete.experience_level,
        goal_30=athlete.goal_30_day,
        goal_6_month=athlete.goal_6_month,
    )
