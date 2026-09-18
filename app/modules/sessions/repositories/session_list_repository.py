"""
Concrete session-list repository (SQLAlchemy), read-only, against the
existing `hamsatech.athletes`, `hamsatech.sessions`,
`hamsatech.shooting_session_log`, and `hamsatech.session_series` tables.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.models.session_series import SessionSeries
from app.models.shooting_session_log import ShootingSessionLog
from app.modules.sessions.repositories.session_list_repository_interface import (
    SessionHistoryRecord,
    SessionListRepositoryInterface,
)

_COMPLETED = Session.end_time.is_not(None)


class SessionListRepository(SessionListRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def count_completed_sessions(self, athlete_id: str) -> int:
        result = await self._session.execute(
            select(func.count(Session.session_id)).where(Session.athlete_id == athlete_id, _COMPLETED)
        )
        return result.scalar_one()

    async def list_completed_sessions(
        self, athlete_id: str, limit: int, offset: int
    ) -> Sequence[SessionHistoryRecord]:
        page_result = await self._session.execute(
            select(Session)
            .where(Session.athlete_id == athlete_id, _COMPLETED)
            .order_by(Session.start_time.desc())
            .limit(limit)
            .offset(offset)
        )
        sessions = page_result.scalars().all()
        if not sessions:
            return []

        session_ids = [s.session_id for s in sessions]

        scores_result = await self._session.execute(
            select(ShootingSessionLog).where(ShootingSessionLog.session_id.in_(session_ids))
        )
        score_by_session_id = {row.session_id: row for row in scores_result.scalars().all()}

        series_count_result = await self._session.execute(
            select(SessionSeries.session_id, func.count(SessionSeries.id))
            .where(SessionSeries.session_id.in_(session_ids))
            .group_by(SessionSeries.session_id)
        )
        series_count_by_session_id: dict[uuid.UUID, int] = dict(series_count_result.tuples().all())

        return [
            SessionHistoryRecord(
                session=s,
                score=score_by_session_id.get(s.session_id),
                series_count=series_count_by_session_id.get(s.session_id, 0),
            )
            for s in sessions
        ]
