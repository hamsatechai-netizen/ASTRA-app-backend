"""
Baseline business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition every sibling
module relies on), enforces that the caller can only create or read
their own `athlete_id`'s baseline (the `athlete_id` in the URL path,
verified — never trusted — against the token-resolved athlete), and
inserts a new `hamsatech.athlete_physiology` row per capture.

Business rules:
- Every submission is a new row — `athlete_physiology` carries no unique
  constraint on `athlete_id`, and a baseline is a point-in-time capture,
  not a single mutable value. Nothing is ever updated or overwritten.
- `recorded_date` is always computed server-side from `utc_now().date()`
  — never accepted from the client, so no future- or past-dated record
  can ever be created by a client-supplied value.
- `session_id` is always `null` for a row created here — this capture
  happens during onboarding, before any training session exists.
- The GET endpoint returns the most recently created row. If none
  exists yet, `BaselineNotFoundException` (404) is raised — never a
  fabricated or default value.
"""

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.baseline.exceptions import (
    AthleteNotFoundException,
    BaselineNotFoundException,
    ForbiddenException,
)
from app.modules.baseline.repositories.baseline_repository_interface import BaselineRepositoryInterface
from app.modules.baseline.schemas.responses import BaselineResponse
from app.utils.datetime import utc_now


class BaselineService:
    """Resolves the authenticated athlete and creates/reads their physiological baseline."""

    def __init__(self, repository: BaselineRepositoryInterface) -> None:
        self._repository = repository

    async def create_baseline(self, phone_number: str, athlete_id: str, resting_hr: int) -> BaselineResponse:
        athlete = await self._get_owned_athlete_or_raise(phone_number, athlete_id)

        row = await self._repository.create_baseline(
            athlete_id=athlete.athlete_id,
            resting_heart_rate=resting_hr,
            recorded_date=utc_now().date(),
        )

        return BaselineResponse(
            athlete_id=row.athlete_id or athlete.athlete_id,
            resting_heart_rate=row.resting_heart_rate,
            recorded_date=row.recorded_date,
            session_id=row.session_id,
            created_at=row.created_at,
        )

    async def get_latest_baseline(self, phone_number: str, athlete_id: str) -> BaselineResponse:
        athlete = await self._get_owned_athlete_or_raise(phone_number, athlete_id)

        row = await self._repository.get_latest_baseline(athlete.athlete_id)
        if row is None:
            raise BaselineNotFoundException()

        return BaselineResponse(
            athlete_id=row.athlete_id or athlete.athlete_id,
            resting_heart_rate=row.resting_heart_rate,
            recorded_date=row.recorded_date,
            session_id=row.session_id,
            created_at=row.created_at,
        )

    async def _get_owned_athlete_or_raise(self, phone_number: str, athlete_id: str) -> HamsaTechAthlete:
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        if athlete.athlete_id != athlete_id:
            raise ForbiddenException("You may only access your own baseline.")
        return athlete
