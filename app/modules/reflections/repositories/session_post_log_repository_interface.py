"""
Reflections repository contract.

Backs the existing `hamsatech.athletes` table (for athlete resolution —
same `get_athlete_by_contact_number` shape as `ScoreRepositoryInterface`
/ `HrStreamRepositoryInterface`, kept as its own narrow interface per the
Interface Segregation rationale already used throughout this project),
the existing `hamsatech.sessions` table (for session ownership checks),
and the existing `hamsatech.session_post_log` table (one row per
session's reflection — `session_id` is UNIQUE on that table, so writes
are upserts, not plain inserts).
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.models.session_post_log import SessionPostLog


class ReflectionRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete/session and upserting a session's reflection."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def get_session_by_id(self, session_id: UUID) -> Session | None:
        """Return the `hamsatech.sessions` row with `session_id`, if any."""

    @abstractmethod
    async def upsert_reflection(
        self,
        *,
        session_id: UUID,
        mood: int | None,
        what_worked: str | None,
        what_didnt: str | None,
    ) -> SessionPostLog:
        """
        Insert a new `session_post_log` row for `session_id`, or update the
        existing one — `session_id` is UNIQUE on that table, so a second
        call for the same session overwrites rather than duplicating/erroring.
        """
