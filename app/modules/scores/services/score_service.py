"""
Score persistence business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition every other module
in this project relies on), enforces that the caller can only save a
score for their own `athlete_id` and their own session, and upserts the
session-level score summary `ScoreEntryBloc` already computes client-side
into `hamsatech.shooting_session_log`. No score value is calculated or
altered here — only persisted.
"""

from uuid import UUID

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.scores.exceptions import (
    AthleteNotFoundException,
    ForbiddenException,
    SessionNotFoundException,
)
from app.modules.scores.repositories.shooting_session_log_repository_interface import (
    ScoreRepositoryInterface,
)
from app.modules.scores.schemas.requests import SaveScoreRequest
from app.modules.scores.schemas.responses import ScoreResponse


class ScoreService:
    """Resolves the authenticated athlete and session, and upserts their score summary."""

    def __init__(self, repository: ScoreRepositoryInterface) -> None:
        self._repository = repository

    async def save_score(
        self, phone_number: str, athlete_id: str, session_id: UUID, payload: SaveScoreRequest
    ) -> ScoreResponse:
        athlete = await self._get_athlete_or_raise(phone_number)
        if athlete.athlete_id != athlete_id:
            raise ForbiddenException("You may only save scores for your own athlete profile.")

        session = await self._repository.get_session_by_id(session_id)
        if session is None:
            raise SessionNotFoundException()
        if session.athlete_id != athlete.athlete_id:
            raise ForbiddenException("You may only save a score for your own session.")

        row = await self._repository.upsert_score(
            session_id=session_id,
            athlete_id=athlete.athlete_id,
            session_date=session.start_time.date(),
            session_type=session.session_type,
            total_shots=payload.total_shots,
            avg_score=payload.avg_score,
            best_series_score=payload.best_series_score,
        )

        return ScoreResponse(
            session_id=row.session_id,
            athlete_id=row.athlete_id,
            total_shots=row.total_shots,
            avg_score=row.avg_score,
            best_series_score=row.best_series_score,
        )

    async def _get_athlete_or_raise(self, phone_number: str) -> HamsaTechAthlete:
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        return athlete
