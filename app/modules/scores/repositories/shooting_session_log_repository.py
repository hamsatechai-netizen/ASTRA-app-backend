"""
Concrete scores repository (SQLAlchemy) against the existing
`hamsatech.athletes`, `hamsatech.sessions`, and `hamsatech.shooting_session_log`
tables. Only ever flushes, never commits — the request-scoped `AsyncSession`
from `app.dependencies.database.get_db` owns the transaction boundary.
"""

from datetime import date
from uuid import UUID

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.models.shooting_session_log import ShootingSessionLog
from app.modules.scores.repositories.shooting_session_log_repository_interface import (
    ScoreRepositoryInterface,
)
from app.utils.datetime import utc_now
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession


class ShootingSessionLogRepository(ScoreRepositoryInterface):
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

    async def upsert_score(
        self,
        *,
        session_id: UUID,
        athlete_id: str,
        session_date: date,
        session_type: str | None,
        total_shots: int,
        avg_score: float,
        best_series_score: float,
    ) -> ShootingSessionLog:
        now = utc_now().replace(tzinfo=None)
        values = {
            "session_id": session_id,
            "athlete_id": athlete_id,
            "session_date": session_date,
            "session_type": session_type,
            "total_shots": total_shots,
            "avg_score": avg_score,
            "best_series_score": best_series_score,
            "updated_at": now,
        }
        insert_stmt = pg_insert(ShootingSessionLog).values(**values)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[ShootingSessionLog.session_id],
            set_={
                "athlete_id": insert_stmt.excluded.athlete_id,
                "session_date": insert_stmt.excluded.session_date,
                "session_type": insert_stmt.excluded.session_type,
                "total_shots": insert_stmt.excluded.total_shots,
                "avg_score": insert_stmt.excluded.avg_score,
                "best_series_score": insert_stmt.excluded.best_series_score,
                "updated_at": insert_stmt.excluded.updated_at,
            },
        ).returning(ShootingSessionLog)
        result = await self._session.execute(upsert_stmt)
        await self._session.flush()
        row: ShootingSessionLog = result.scalar_one()
        return row
