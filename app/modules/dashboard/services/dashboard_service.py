"""
Dashboard business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition every other mobile
module relies on), enforces that the caller can only read their own
`athlete_id` (part of the URL, like every other `/api/mobile` endpoint),
and computes a factual weekly training summary — a real date-filtered
COUNT/AVG over already-persisted data, not a derived wellness score.

Deliberately does not compute Streak or AI insights (see
`DashboardHomeResponse`'s docstring for why) or any of
Readiness/Recovery/Stress/Steady (never requested by the Flutter client at
this endpoint, and no legitimate algorithm exists for them yet).
"""

from datetime import datetime, timedelta

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.dashboard.exceptions import AthleteNotFoundException, ForbiddenException
from app.modules.dashboard.repositories.dashboard_repository_interface import DashboardRepositoryInterface
from app.modules.dashboard.schemas.responses import DashboardHomeResponse
from app.utils.datetime import utc_now


class DashboardService:
    """Resolves the authenticated athlete and builds their dashboard home summary."""

    def __init__(self, repository: DashboardRepositoryInterface) -> None:
        self._repository = repository

    async def get_home(self, phone_number: str, athlete_id: str) -> DashboardHomeResponse:
        athlete = await self._get_owned_athlete_or_raise(phone_number, athlete_id)

        week_start = _start_of_week_utc_naive()
        sessions_this_week = await self._repository.count_completed_sessions_since(
            athlete.athlete_id, week_start
        )
        weekly_avg_score = await self._repository.get_average_score_since(athlete.athlete_id, week_start)

        return DashboardHomeResponse(
            athlete_id=athlete.athlete_id,
            athlete_name=athlete.athlete_name,
            sessions_this_week=sessions_this_week,
            weekly_avg_score=weekly_avg_score,
        )

    async def _get_owned_athlete_or_raise(self, phone_number: str, athlete_id: str) -> HamsaTechAthlete:
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        if athlete.athlete_id != athlete_id:
            raise ForbiddenException("You may only access your own dashboard.")
        return athlete


def _start_of_week_utc_naive() -> datetime:
    """
    Monday 00:00:00 of the current UTC week, as a naive datetime — matches
    `Session.start_time`'s storage convention (`DateTime(timezone=False)`,
    always written via `utc_now().replace(tzinfo=None)` — see
    `app.modules.sessions.repositories.session_repository.create`).

    Computed in UTC, not the athlete's local time: this backend has no
    stored timezone for any athlete, so UTC week boundaries are the only
    honest choice available — not a fabrication, just a documented
    approximation that may differ from the athlete's local midnight by a
    few hours.
    """
    today = utc_now()
    start_of_day = today.replace(hour=0, minute=0, second=0, microsecond=0)
    return (start_of_day - timedelta(days=today.weekday())).replace(tzinfo=None)
