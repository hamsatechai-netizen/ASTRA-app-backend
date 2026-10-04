"""
Concrete series repository (SQLAlchemy) against the existing
`hamsatech.athletes`/`hamsatech.sessions` tables and this project's own
`hamsatech.session_series` table. Only ever flushes, never commits — the
request-scoped `AsyncSession` from `app.dependencies.database.get_db`
owns the transaction boundary.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.models.session_series import SessionSeries
from app.modules.series.repositories.session_series_repository_interface import (
    SeriesRepositoryInterface,
)
from app.utils.datetime import utc_now


class SessionSeriesRepository(SeriesRepositoryInterface):
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

    async def upsert_series(
        self,
        *,
        session_id: UUID,
        series_number: int,
        total_score: float,
        shots_fired: int,
    ) -> SessionSeries:
        now = utc_now().replace(tzinfo=None)
        # `id`/`created_at` are deliberately omitted from `values` — their
        # DB defaults apply only on insert; on conflict they're absent from
        # `set_` too, so an existing row's identity/created_at is preserved.
        insert_stmt = pg_insert(SessionSeries).values(
            session_id=session_id,
            series_number=series_number,
            total_score=total_score,
            shots_fired=shots_fired,
            updated_at=now,
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[SessionSeries.session_id, SessionSeries.series_number],
            set_={
                "total_score": insert_stmt.excluded.total_score,
                "shots_fired": insert_stmt.excluded.shots_fired,
                "updated_at": insert_stmt.excluded.updated_at,
            },
        ).returning(SessionSeries)
        result = await self._session.execute(upsert_stmt)
        await self._session.flush()
        row: SessionSeries = result.scalar_one()
        return row
