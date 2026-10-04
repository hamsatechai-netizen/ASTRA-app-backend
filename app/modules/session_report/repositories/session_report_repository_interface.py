"""
Session-report repository contract.

Backs the existing `hamsatech.athletes` table (for athlete resolution —
same `get_athlete_by_contact_number` shape as every sibling module's
repository, kept as its own narrow interface per the Interface
Segregation rationale already used throughout this project), the existing
`hamsatech.sessions` table (for session metadata and ownership checks),
and the read side of `hamsatech.hr_stream`, `hamsatech.shooting_session_log`,
`hamsatech.session_series`, and `hamsatech.session_post_log` — every table
a training session's data already lives in.

This interface is read-only: the report never writes to any table. Each
existing write path (heart-rate ingestion, scores, series, reflections,
session lifecycle) keeps owning its own writes; this module only
aggregates what they've already persisted.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.models.session_post_log import SessionPostLog
from app.models.session_series import SessionSeries
from app.models.shooting_session_log import ShootingSessionLog


@dataclass(frozen=True, slots=True)
class HrAggregateRecord:
    """
    Heart-rate statistics for one session, computed entirely in SQL
    (`COUNT`/`AVG`/`MIN`/`MAX`, plus two `ORDER BY ... LIMIT 1` lookups for
    the first/last sample) — never by loading every `hr_stream` row for the
    session into Python. All fields are `None`/zero when the session has no
    HR samples, matching the existing `SessionHrResponse` convention of
    never fabricating a value.
    """

    sample_count: int
    avg_hr: int | None
    min_hr: int | None
    max_hr: int | None
    first_hr: int | None
    last_hr: int | None


class SessionReportRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete/session and reading every table a report needs."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def get_session_by_id(self, session_id: UUID) -> Session | None:
        """Return the `hamsatech.sessions` row with `session_id`, if any."""

    @abstractmethod
    async def get_hr_aggregate_for_session(self, session_id: UUID) -> HrAggregateRecord:
        """Return SQL-computed HR statistics for `session_id` (zero/None fields if no samples)."""

    @abstractmethod
    async def get_score_for_session(self, session_id: UUID) -> ShootingSessionLog | None:
        """Return the `shooting_session_log` row for `session_id`, if a score summary was saved."""

    @abstractmethod
    async def get_series_for_session(self, session_id: UUID) -> Sequence[SessionSeries]:
        """Return every `session_series` row for `session_id`, ordered by `series_number` ascending."""

    @abstractmethod
    async def get_reflection_for_session(self, session_id: UUID) -> SessionPostLog | None:
        """Return the `session_post_log` row for `session_id`, if a reflection was saved."""
