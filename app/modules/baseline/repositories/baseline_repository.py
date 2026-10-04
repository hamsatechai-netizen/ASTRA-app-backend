"""
Concrete baseline repository (SQLAlchemy) against the existing
`hamsatech.athletes` and `hamsatech.athlete_physiology` tables. Only ever
flushes, never commits — the request-scoped `AsyncSession` from
`app.dependencies.database.get_db` owns the transaction boundary.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_physiology import AthletePhysiology
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.baseline.repositories.baseline_repository_interface import BaselineRepositoryInterface


class BaselineRepository(BaselineRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def create_baseline(
        self, *, athlete_id: str, resting_heart_rate: int, recorded_date: date
    ) -> AthletePhysiology:
        row = AthletePhysiology(
            athlete_id=athlete_id,
            resting_heart_rate=resting_heart_rate,
            recorded_date=recorded_date,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_latest_baseline(self, athlete_id: str) -> AthletePhysiology | None:
        result = await self._session.execute(
            select(AthletePhysiology)
            .where(AthletePhysiology.athlete_id == athlete_id)
            .order_by(
                AthletePhysiology.created_at.desc().nulls_last(),
                AthletePhysiology.recorded_date.desc().nulls_last(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()
