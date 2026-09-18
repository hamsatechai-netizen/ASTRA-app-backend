"""
Session-list repository contract.

Backs the existing `hamsatech.athletes`, `hamsatech.sessions`,
`hamsatech.shooting_session_log`, and `hamsatech.session_series` tables —
every table a session-history summary needs. Kept as its own interface,
separate from `SessionRepositoryInterface` (which only handles single-session
create/complete): listing is new functionality, not a duplicate of
existing create/complete behavior, and this keeps that interface (and its
existing tests) completely untouched. Read-only, same rationale as
`app.modules.session_report.repositories.session_report_repository_interface`.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.models.shooting_session_log import ShootingSessionLog


@dataclass(frozen=True, slots=True)
class SessionHistoryRecord:
    """One session plus its score summary (if any) and series count — everything one list row needs."""

    session: Session
    score: ShootingSessionLog | None
    series_count: int


class SessionListRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete and paging through their completed sessions."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def count_completed_sessions(self, athlete_id: str) -> int:
        """Count `athlete_id`'s completed sessions (`end_time IS NOT NULL`)."""

    @abstractmethod
    async def list_completed_sessions(
        self, athlete_id: str, limit: int, offset: int
    ) -> Sequence[SessionHistoryRecord]:
        """
        Return one page of `athlete_id`'s completed sessions, newest first
        (`start_time` descending), with each session's score summary and
        series count attached. Issues a fixed number of queries regardless
        of page size (one for the page of sessions, one batched lookup for
        scores, one batched lookup for series counts) — never one query per
        row, same convention as `SessionReportRepository`.
        """
