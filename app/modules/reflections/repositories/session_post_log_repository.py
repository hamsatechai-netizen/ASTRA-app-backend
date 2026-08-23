"""
Concrete reflections repository (SQLAlchemy) against the existing
`hamsatech.athletes`, `hamsatech.sessions`, and `hamsatech.session_post_log`
tables. Only ever flushes, never commits — the request-scoped `AsyncSession`
from `app.dependencies.database.get_db` owns the transaction boundary.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.models.session_post_log import SessionPostLog
from app.modules.reflections.repositories.session_post_log_repository_interface import (
    ReflectionRepositoryInterface,
)


class SessionPostLogRepository(ReflectionRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def get_session_by_id(self, session_id: UUID) -> Session | None:
        result = await self._session.execute(select(Session).where(Session.session_id == session_id))
        return result.scalar_one_or_none()

    async def upsert_reflection(
        self,
        *,
        session_id: UUID,
        mood: int | None,
        what_worked: str | None,
        what_didnt: str | None,
    ) -> SessionPostLog:
        # `id` is deliberately omitted — its DEFAULT gen_random_uuid() applies
        # only on insert; on conflict, `id`/`created_at` are left untouched
        # (not present in `set_` below), preserving the original row identity.
        insert_stmt = pg_insert(SessionPostLog).values(
            session_id=session_id,
            mood=mood,
            what_worked=what_worked,
            what_didnt=what_didnt,
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[SessionPostLog.session_id],
            set_={
                "mood": insert_stmt.excluded.mood,
                "what_worked": insert_stmt.excluded.what_worked,
                "what_didnt": insert_stmt.excluded.what_didnt,
            },
        ).returning(SessionPostLog)
        result = await self._session.execute(upsert_stmt)
        await self._session.flush()
        row: SessionPostLog = result.scalar_one()
        return row
