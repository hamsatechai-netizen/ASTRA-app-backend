"""
Reflection persistence business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition every other module
in this project relies on), enforces that the caller can only save a
reflection for their own `athlete_id` and their own session, and upserts
the mood/what-worked/what-didn't values `ReflectScreen` already collects
client-side into `hamsatech.session_post_log`. No value is calculated or
altered here — only persisted.
"""

from uuid import UUID

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.reflections.exceptions import (
    AthleteNotFoundException,
    ForbiddenException,
    SessionNotFoundException,
)
from app.modules.reflections.repositories.session_post_log_repository_interface import (
    ReflectionRepositoryInterface,
)
from app.modules.reflections.schemas.requests import SaveReflectionRequest
from app.modules.reflections.schemas.responses import ReflectionResponse


class ReflectionService:
    """Resolves the authenticated athlete and session, and upserts their reflection."""

    def __init__(self, repository: ReflectionRepositoryInterface) -> None:
        self._repository = repository

    async def save_reflection(
        self, phone_number: str, athlete_id: str, session_id: UUID, payload: SaveReflectionRequest
    ) -> ReflectionResponse:
        athlete = await self._get_athlete_or_raise(phone_number)
        if athlete.athlete_id != athlete_id:
            raise ForbiddenException("You may only save reflections for your own athlete profile.")

        session = await self._repository.get_session_by_id(session_id)
        if session is None:
            raise SessionNotFoundException()
        if session.athlete_id != athlete.athlete_id:
            raise ForbiddenException("You may only save a reflection for your own session.")

        row = await self._repository.upsert_reflection(
            session_id=session_id,
            mood=payload.mood,
            what_worked=payload.what_worked,
            what_didnt=payload.what_didnt,
        )

        return ReflectionResponse(
            session_id=session_id,
            mood=row.mood,
            what_worked=row.what_worked,
            what_didnt=row.what_didnt,
        )

    async def _get_athlete_or_raise(self, phone_number: str) -> HamsaTechAthlete:
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        return athlete
