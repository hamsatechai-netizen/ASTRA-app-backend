"""
Streak repository contract.

Backs the existing `hamsatech.athletes` and `hamsatech.sessions` tables
only — no new table, column, or persistence mechanism. Kept as its own
narrow interface (same Interface Segregation rationale documented in
`app.modules.sessions.repositories.session_repository_interface`).

Deliberately exposes nothing for "current streak" or "longest streak"
directly: those are derived, in Python, from the plain list of distinct
active dates this interface returns — the calculation is business logic
(`app.modules.streak.services.streak_service`), not a repository concern.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date

from app.models.hamsatech_athlete import HamsaTechAthlete


class StreakRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete and reading their completed-session dates."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def get_completed_session_dates(self, athlete_id: str, on_or_before: date) -> Sequence[date]:
        """
        Return the distinct UTC calendar dates (`DATE(start_time)`) on which
        `athlete_id` has at least one completed session (`end_time IS NOT
        NULL`), descending (most recent first).

        `on_or_before` excludes any date after it — a defensive guard
        against a clock-skewed or otherwise future-dated row ever
        participating in a streak calculation; it is never fabricated away,
        just never counted.
        """
