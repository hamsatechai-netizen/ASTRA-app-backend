"""
Concrete dashboard repository (SQLAlchemy) against the existing
`hamsatech.athletes`, `hamsatech.sessions`, and `hamsatech.shooting_session_log`
tables. Read-only. Issues one query per data source (never one query per
row) — same fixed-query-count convention as
`app.modules.session_report.repositories.session_report_repository`.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.models.shooting_session_log import ShootingSessionLog
from app.modules.dashboard.repositories.dashboard_repository_interface import (
    DashboardRepositoryInterface,
)


class DashboardRepository(DashboardRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def count_completed_sessions_since(self, athlete_id: str, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count(Session.session_id)).where(
                Session.athlete_id == athlete_id,
                Session.start_time >= since,
                Session.end_time.is_not(None),
            )
        )
        return result.scalar_one()

    async def get_average_score_since(self, athlete_id: str, since: datetime) -> float | None:
        result = await self._session.execute(
            select(func.avg(ShootingSessionLog.avg_score))
            .select_from(Session)
            .join(ShootingSessionLog, ShootingSessionLog.session_id == Session.session_id)
            .where(
                Session.athlete_id == athlete_id,
                Session.start_time >= since,
                Session.end_time.is_not(None),
            )
        )
        average = result.scalar_one_or_none()
        return float(average) if average is not None else None
