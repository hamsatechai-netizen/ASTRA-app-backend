"""
Scores repository contract.

Backs the existing `hamsatech.athletes` table (for athlete resolution —
same `get_athlete_by_contact_number` shape as `SessionRepositoryInterface`
/ `HrStreamRepositoryInterface`, kept as its own narrow interface per the
Interface Segregation rationale already used throughout this project),
the existing `hamsatech.sessions` table (for session ownership checks),
and the existing `hamsatech.shooting_session_log` table (one row per
session's score summary — `session_id` is that table's real primary key,
so writes are upserts, not plain inserts).
"""

from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.models.shooting_session_log import ShootingSessionLog


class ScoreRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete/session and upserting a session's score."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def get_session_by_id(self, session_id: UUID) -> Session | None:
        """Return the `hamsatech.sessions` row with `session_id`, if any."""

    @abstractmethod
    async def upsert_score(
        self,
        *,
        session_id: UUID,
        athlete_id: str,
        session_date: date,
        session_type: str | None,
        total_shots: int,
        avg_score: float,
        best_series_score: float,
    ) -> ShootingSessionLog:
        """
        Insert a new `shooting_session_log` row for `session_id`, or update the
        existing one — `session_id` is that table's primary key, so a second
        call for the same session overwrites rather than duplicating/erroring.
        """
