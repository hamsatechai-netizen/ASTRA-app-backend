"""
Concrete session-report repository (SQLAlchemy) — read-only, against the
existing `hamsatech.athletes`, `hamsatech.sessions`, `hamsatech.hr_stream`,
`hamsatech.shooting_session_log`, `hamsatech.session_series`, and
`hamsatech.session_post_log` tables. Issues one query per data source
(never one query per row), so the report's total query count stays fixed
regardless of how many HR samples or series a session has.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hr_stream import HrStream
from app.models.session import Session
from app.models.session_post_log import SessionPostLog
from app.models.session_series import SessionSeries
from app.models.shooting_session_log import ShootingSessionLog
from app.modules.session_report.repositories.session_report_repository_interface import (
    HrAggregateRecord,
    SessionReportRepositoryInterface,
)


class SessionReportRepository(SessionReportRepositoryInterface):
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

    async def get_hr_aggregate_for_session(self, session_id: UUID) -> HrAggregateRecord:
        # A sample with a null `heart_rate` or `recorded_at` can't contribute to any
        # of these statistics — same skip condition `HrStreamRepository.get_samples_for_session`
        # already applies when reading samples back for the chart endpoint.
        valid_sample = (
            HrStream.session_id == session_id,
            HrStream.heart_rate.is_not(None),
            HrStream.recorded_at.is_not(None),
        )

        aggregate_result = await self._session.execute(
            select(
                func.count(HrStream.id),
                func.avg(HrStream.heart_rate),
                func.min(HrStream.heart_rate),
                func.max(HrStream.heart_rate),
            ).where(*valid_sample)
        )
        sample_count, avg_hr, min_hr, max_hr = aggregate_result.one()

        if sample_count == 0:
            return HrAggregateRecord(
                sample_count=0, avg_hr=None, min_hr=None, max_hr=None, first_hr=None, last_hr=None
            )

        first_result = await self._session.execute(
            select(HrStream.heart_rate).where(*valid_sample).order_by(HrStream.recorded_at.asc()).limit(1)
        )
        last_result = await self._session.execute(
            select(HrStream.heart_rate).where(*valid_sample).order_by(HrStream.recorded_at.desc()).limit(1)
        )

        return HrAggregateRecord(
            sample_count=sample_count,
            avg_hr=round(float(avg_hr)),
            min_hr=min_hr,
            max_hr=max_hr,
            first_hr=first_result.scalar_one_or_none(),
            last_hr=last_result.scalar_one_or_none(),
        )

    async def get_score_for_session(self, session_id: UUID) -> ShootingSessionLog | None:
        result = await self._session.execute(
            select(ShootingSessionLog).where(ShootingSessionLog.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_series_for_session(self, session_id: UUID) -> Sequence[SessionSeries]:
        result = await self._session.execute(
            select(SessionSeries)
            .where(SessionSeries.session_id == session_id)
            .order_by(SessionSeries.series_number.asc())
        )
        return result.scalars().all()

    async def get_reflection_for_session(self, session_id: UUID) -> SessionPostLog | None:
        result = await self._session.execute(
            select(SessionPostLog).where(SessionPostLog.session_id == session_id)
        )
        return result.scalar_one_or_none()
