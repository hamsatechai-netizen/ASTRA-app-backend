"""
Streak business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition every sibling
module relies on), enforces that the caller can only read their own
`athlete_id`'s streak, and derives current/longest streak from the
athlete's real, already-persisted `hamsatech.sessions` history — never a
fabricated, simulated, or estimated value.

Business rules (confirmed product decisions, not silently chosen):
- An "active day" is a UTC calendar date with >=1 completed session
  (`end_time IS NOT NULL`). Incomplete sessions never count.
- Multiple sessions on the same UTC date count once.
- A future-dated row (clock skew or bad data) never participates — the
  repository excludes anything after "today" outright.
- The current streak does NOT require a session *today* to still report
  correctly: if the most recent active day is today or yesterday, the
  unbroken run up to that day counts in full. Any gap of a full missed day
  beyond that breaks it back to a fresh count — there is no grace day.
- Longest streak is the longest run of consecutive UTC calendar dates
  found anywhere in the athlete's history, independent of whether the
  current streak is currently broken.
- Both values are computed live on every request; neither is persisted as
  its own stored value anywhere.

Timezone caveat (documented, not hidden): "today"/"yesterday"/day
boundaries are all computed in UTC, because no athlete timezone is
collected or stored anywhere in this system. For an athlete far from UTC,
a session near their local midnight can be attributed to the "wrong" UTC
calendar day relative to how they'd describe it themselves. A precise fix
requires collecting and storing an athlete timezone, which does not exist
today and is out of scope here.
"""

from collections.abc import Sequence
from datetime import date

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.streak.exceptions import AthleteNotFoundException, ForbiddenException
from app.modules.streak.repositories.streak_repository_interface import StreakRepositoryInterface
from app.modules.streak.schemas.responses import StreakResponse
from app.utils.datetime import utc_now

_MAX_GAP_FOR_CURRENT_STREAK_TO_STILL_COUNT = 1  # today or yesterday — not two or more days ago
_CONSECUTIVE_DAY_GAP = 1


class StreakService:
    """Resolves the authenticated athlete and computes their current/longest streak."""

    def __init__(self, repository: StreakRepositoryInterface) -> None:
        self._repository = repository

    async def get_streak(self, phone_number: str, athlete_id: str) -> StreakResponse:
        athlete = await self._get_owned_athlete_or_raise(phone_number, athlete_id)

        today = utc_now().date()
        dates = await self._repository.get_completed_session_dates(athlete.athlete_id, today)
        current_streak, longest_streak = _compute_streaks(dates, today)

        return StreakResponse(
            athlete_id=athlete.athlete_id,
            current_streak=current_streak,
            longest_streak=longest_streak,
            last_active_date=dates[0] if dates else None,
        )

    async def _get_owned_athlete_or_raise(self, phone_number: str, athlete_id: str) -> HamsaTechAthlete:
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        if athlete.athlete_id != athlete_id:
            raise ForbiddenException("You may only access your own streak.")
        return athlete


def _compute_streaks(dates: Sequence[date], today: date) -> tuple[int, int]:
    """
    `dates` must be distinct and sorted descending (most recent first) —
    exactly what `StreakRepositoryInterface.get_completed_session_dates`
    returns. Never fabricates a value: an empty `dates` yields `(0, 0)`.
    """
    if not dates:
        return 0, 0

    longest_streak = 1
    run = 1
    for i in range(1, len(dates)):
        if (dates[i - 1] - dates[i]).days == _CONSECUTIVE_DAY_GAP:
            run += 1
        else:
            longest_streak = max(longest_streak, run)
            run = 1
    longest_streak = max(longest_streak, run)

    most_recent = dates[0]
    if (today - most_recent).days > _MAX_GAP_FOR_CURRENT_STREAK_TO_STILL_COUNT:
        return 0, longest_streak

    current_streak = 1
    cursor = most_recent
    for d in dates[1:]:
        if (cursor - d).days == _CONSECUTIVE_DAY_GAP:
            current_streak += 1
            cursor = d
        else:
            break

    return current_streak, longest_streak
