"""
Sessions business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition `HeartRateService`
and `PsychologyAssessmentService` rely on), enforces that the caller can
only create a session for their own `athlete_id` (the athlete ID is part
of the URL, unlike v2 endpoints which resolve it purely from the token),
and creates the row in `hamsatech.sessions`.
"""

import uuid

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.sessions.exceptions import (
    AthleteNotFoundException,
    ForbiddenException,
    SessionNotFoundException,
)
from app.modules.sessions.repositories.session_repository_interface import SessionRepositoryInterface
from app.modules.sessions.schemas.requests import CreateSessionRequest
from app.modules.sessions.schemas.responses import SessionResponse
from app.utils.datetime import utc_now


class SessionService:
    """Resolves the authenticated athlete and creates a new training session for them."""

    def __init__(self, repository: SessionRepositoryInterface) -> None:
        self._repository = repository

    async def create_session(
        self, phone_number: str, athlete_id: str, payload: CreateSessionRequest
    ) -> SessionResponse:
        athlete = await self._get_athlete_or_raise(phone_number)
        if athlete.athlete_id != athlete_id:
            raise ForbiddenException("You may only create sessions for your own athlete profile.")

        row = await self._repository.create(athlete.athlete_id, payload.session_type)

        return SessionResponse(
            session_id=row.session_id,
            athlete_id=row.athlete_id,
            session_type=row.session_type,
            start_time=row.start_time,
            end_time=row.end_time,
        )

    async def complete_session(
        self, phone_number: str, athlete_id: str, session_id: uuid.UUID
    ) -> SessionResponse:
        athlete = await self._get_athlete_or_raise(phone_number)
        if athlete.athlete_id != athlete_id:
            raise ForbiddenException("You may only complete sessions for your own athlete profile.")

        row = await self._repository.get_by_id(session_id)
        if row is None:
            raise SessionNotFoundException()
        if row.athlete_id != athlete.athlete_id:
            raise ForbiddenException("You may only complete your own session.")

        if row.end_time is None:
            row = await self._repository.complete(row, utc_now())

        return SessionResponse(
            session_id=row.session_id,
            athlete_id=row.athlete_id,
            session_type=row.session_type,
            start_time=row.start_time,
            end_time=row.end_time,
        )

    async def _get_athlete_or_raise(self, phone_number: str) -> HamsaTechAthlete:
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        return athlete
