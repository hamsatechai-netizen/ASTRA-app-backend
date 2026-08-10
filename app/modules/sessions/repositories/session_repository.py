"""
Concrete sessions repository (SQLAlchemy) against the existing
`hamsatech.athletes` and `hamsatech.sessions` tables. Only ever flushes,
never commits — the request-scoped `AsyncSession` from
`app.dependencies.database.get_db` owns the transaction boundary.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.modules.sessions.repositories.session_repository_interface import SessionRepositoryInterface
from app.utils.datetime import utc_now


class SessionRepository(SessionRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def create(self, athlete_id: str, session_type: str | None) -> Session:
        row = Session(
            session_id=uuid.uuid4(),
            athlete_id=athlete_id,
            session_type=session_type,
            start_time=utc_now().replace(tzinfo=None),
        )
        self._session.add(row)
        await self._session.flush()
        return row
