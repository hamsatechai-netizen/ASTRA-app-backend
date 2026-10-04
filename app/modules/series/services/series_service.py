"""
Series persistence business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition every other module
in this project relies on), enforces that the caller can only save a
series for their own `athlete_id` and their own session, and upserts the
series values `ScoreEntryBloc._syncSeries` already computes client-side
into `hamsatech.session_series`. No value is calculated or altered here
— only persisted.
"""

from uuid import UUID

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.series.exceptions import (
    AthleteNotFoundException,
    ForbiddenException,
    SessionNotFoundException,
)
from app.modules.series.repositories.session_series_repository_interface import (
    SeriesRepositoryInterface,
)
from app.modules.series.schemas.requests import SaveSeriesRequest
from app.modules.series.schemas.responses import SeriesResponse


class SeriesService:
    """Resolves the authenticated athlete and session, and upserts their series."""

    def __init__(self, repository: SeriesRepositoryInterface) -> None:
        self._repository = repository

    async def save_series(
        self, phone_number: str, athlete_id: str, session_id: UUID, payload: SaveSeriesRequest
    ) -> SeriesResponse:
        athlete = await self._get_athlete_or_raise(phone_number)
        if athlete.athlete_id != athlete_id:
            raise ForbiddenException("You may only save series for your own athlete profile.")

        session = await self._repository.get_session_by_id(session_id)
        if session is None:
            raise SessionNotFoundException()
        if session.athlete_id != athlete.athlete_id:
            raise ForbiddenException("You may only save a series for your own session.")

        row = await self._repository.upsert_series(
            session_id=session_id,
            series_number=payload.series_number,
            total_score=payload.total_score,
            shots_fired=payload.shots_fired,
        )

        return SeriesResponse(
            session_id=session_id,
            series_number=row.series_number,
            total_score=row.total_score,
            shots_fired=row.shots_fired,
        )

    async def _get_athlete_or_raise(self, phone_number: str) -> HamsaTechAthlete:
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        return athlete
