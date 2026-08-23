"""
Series repository contract.

Backs the existing `hamsatech.athletes` table (for athlete resolution —
same `get_athlete_by_contact_number` shape as `ScoreRepositoryInterface`
/ `ReflectionRepositoryInterface`, kept as its own narrow interface per
the Interface Segregation rationale already used throughout this
project), the existing `hamsatech.sessions` table (for session ownership
checks), and `hamsatech.session_series` (one row per
`(session_id, series_number)` — that pair is UNIQUE, so writes are
upserts, not plain inserts).
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.models.session_series import SessionSeries


class SeriesRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete/session and upserting a session's series."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def get_session_by_id(self, session_id: UUID) -> Session | None:
        """Return the `hamsatech.sessions` row with `session_id`, if any."""

    @abstractmethod
    async def upsert_series(
        self,
        *,
        session_id: UUID,
        series_number: int,
        total_score: float,
        shots_fired: int,
    ) -> SessionSeries:
        """
        Insert a new `session_series` row for `(session_id, series_number)`, or
        update the existing one — that pair is UNIQUE, so a second call for
        the same series overwrites rather than duplicating/erroring.
        """
