"""
Daily check-in business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition every sibling
module relies on), enforces that the caller can only submit a check-in
for their own `athlete_id` (sent in the body by the existing Flutter
contract, verified — never trusted — against the token-resolved athlete),
and upserts the athlete's check-in for the current UTC calendar day.

Business rules (per the approved Daily Check-in specification):
- One check-in per athlete per UTC calendar day
  (`hamsatech.daily_checkins`'s `UNIQUE(athlete_id, checkin_date)`).
- A second submission on the same UTC day updates the existing row —
  `created_at` is preserved, `updated_at` changes. Never a duplicate row.
- `checkin_date` is always computed server-side from `utc_now().date()` —
  never accepted from the client, so no future- or past-dated record can
  ever be created by a client-supplied value.
- Historical rows are never deleted or overwritten by a later day's
  submission — only the current UTC day's row is ever touched.
- No value here is calculated or altered beyond straightforward
  persistence — mood/energy_level/sleep_band/tags/notes are stored
  exactly as submitted, never derived into Readiness/Recovery/Stress/
  Steady or any other metric.

Timezone caveat (documented, not hidden): the UTC calendar-day boundary
is the same approximation already used by `app.modules.streak`'s
current-streak calculation and the dashboard's `sessions_this_week` — no
athlete timezone is collected or stored anywhere in this system.
"""

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.checkin.exceptions import AthleteNotFoundException, ForbiddenException
from app.modules.checkin.repositories.checkin_repository_interface import CheckinRepositoryInterface
from app.modules.checkin.schemas.requests import SaveCheckinRequest
from app.modules.checkin.schemas.responses import CheckinResponse
from app.utils.datetime import utc_now


class CheckinService:
    """Resolves the authenticated athlete and upserts their check-in for the current UTC day."""

    def __init__(self, repository: CheckinRepositoryInterface) -> None:
        self._repository = repository

    async def save_checkin(self, phone_number: str, payload: SaveCheckinRequest) -> CheckinResponse:
        athlete = await self._get_athlete_or_raise(phone_number)
        if athlete.athlete_id != payload.athlete_id:
            raise ForbiddenException("You may only submit a check-in for your own athlete profile.")

        checkin_date = utc_now().date()
        row = await self._repository.upsert_checkin(
            athlete_id=athlete.athlete_id,
            checkin_date=checkin_date,
            mood=payload.mood,
            energy_level=payload.energy_level,
            sleep_band=payload.sleep_band,
            tags=list(payload.tags) if payload.tags else None,
            notes=payload.notes,
        )

        return CheckinResponse(
            athlete_id=row.athlete_id,
            checkin_date=row.checkin_date,
            mood=row.mood,
            energy_level=row.energy_level,
            sleep_band=row.sleep_band,
            tags=row.tags or [],
            notes=row.notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _get_athlete_or_raise(self, phone_number: str) -> HamsaTechAthlete:
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        return athlete
