"""
Concrete athlete-details repository (SQLAlchemy) against the existing
`hamsatech.athlete_details` table. Only ever flushes, never commits — the
request-scoped `AsyncSession` from `app.dependencies.database.get_db`
owns the transaction boundary.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete_details import HamsaTechAthleteDetails
from app.modules.onboarding.repositories.athlete_details_repository_interface import (
    AthleteDetailsRepositoryInterface,
)


class AthleteDetailsRepository(AthleteDetailsRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_athlete_id(self, athlete_id: str) -> HamsaTechAthleteDetails | None:
        result = await self._session.execute(
            select(HamsaTechAthleteDetails).where(HamsaTechAthleteDetails.athlete_id == athlete_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, athlete_id: str, *, class_: str, school_name: str, academic_performance: str
    ) -> HamsaTechAthleteDetails:
        details = HamsaTechAthleteDetails(
            athlete_id=athlete_id,
            class_=class_,
            school_name=school_name,
            academic_performance=academic_performance,
        )
        self._session.add(details)
        await self._session.flush()
        return details

    async def update(
        self,
        details: HamsaTechAthleteDetails,
        *,
        class_: str,
        school_name: str,
        academic_performance: str,
    ) -> HamsaTechAthleteDetails:
        details.class_ = class_
        details.school_name = school_name
        details.academic_performance = academic_performance
        await self._session.flush()
        return details
