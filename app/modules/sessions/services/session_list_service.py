"""
Session-list business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition every sibling module
relies on), enforces that the caller can only list their own `athlete_id`'s
sessions, and returns a real, paginated page of already-persisted data —
no fabricated scores, no invented metrics, no Readiness/Recovery/Stress/
Steady, no streak, no AI insights.
"""

from math import ceil

from app.common.responses import PaginatedResponse, PaginationMeta
from app.dependencies.pagination import PaginationParams
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.sessions.exceptions import AthleteNotFoundException, ForbiddenException
from app.modules.sessions.repositories.session_list_repository_interface import (
    SessionHistoryRecord,
    SessionListRepositoryInterface,
)
from app.modules.sessions.schemas.responses import SessionHistoryItem


class SessionListService:
    """Resolves the authenticated athlete and builds a paginated page of their session history."""

    def __init__(self, repository: SessionListRepositoryInterface) -> None:
        self._repository = repository

    async def list_sessions(
        self, phone_number: str, athlete_id: str, pagination: PaginationParams
    ) -> PaginatedResponse[SessionHistoryItem]:
        athlete = await self._get_owned_athlete_or_raise(phone_number, athlete_id)

        total = await self._repository.count_completed_sessions(athlete.athlete_id)
        records = await self._repository.list_completed_sessions(
            athlete.athlete_id, pagination.page_size, pagination.offset
        )

        return PaginatedResponse(
            data=[_to_item(record) for record in records],
            meta=PaginationMeta(
                total=total,
                page=pagination.page,
                page_size=pagination.page_size,
                total_pages=ceil(total / pagination.page_size) if total else 0,
            ),
        )

    async def _get_owned_athlete_or_raise(self, phone_number: str, athlete_id: str) -> HamsaTechAthlete:
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        if athlete.athlete_id != athlete_id:
            raise ForbiddenException("You may only list your own sessions.")
        return athlete


def _to_item(record: SessionHistoryRecord) -> SessionHistoryItem:
    session = record.session
    score = record.score
    # `end_time` is guaranteed non-null here: the repository only ever
    # selects completed sessions (`end_time IS NOT NULL`).
    assert session.end_time is not None
    duration_seconds = int((session.end_time - session.start_time).total_seconds())

    return SessionHistoryItem(
        session_id=session.session_id,
        session_type=session.session_type,
        start_time=session.start_time,
        end_time=session.end_time,
        duration_seconds=duration_seconds,
        avg_score=float(score.avg_score) if score is not None and score.avg_score is not None else None,
        best_series_score=(
            float(score.best_series_score)
            if score is not None and score.best_series_score is not None
            else None
        ),
        total_shots=score.total_shots if score is not None else None,
        series_count=record.series_count,
    )
