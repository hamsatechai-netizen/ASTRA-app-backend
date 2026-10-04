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

    async def create_step_5(
        self,
        athlete_id: str,
        *,
        diet_type: str,
        outside_food_frequency: str,
        sleep_time: str,
        wake_time: str,
    ) -> HamsaTechAthleteDetails:
        details = HamsaTechAthleteDetails(
            athlete_id=athlete_id,
            diet_type=diet_type,
            outside_food_frequency=outside_food_frequency,
            sleep_time=sleep_time,
            wake_time=wake_time,
        )
        self._session.add(details)
        await self._session.flush()
        return details

    async def update_step_5(
        self,
        details: HamsaTechAthleteDetails,
        *,
        diet_type: str,
        outside_food_frequency: str,
        sleep_time: str,
        wake_time: str,
    ) -> HamsaTechAthleteDetails:
        details.diet_type = diet_type
        details.outside_food_frequency = outside_food_frequency
        details.sleep_time = sleep_time
        details.wake_time = wake_time
        await self._session.flush()
        return details

    async def create_step_6(
        self,
        athlete_id: str,
        *,
        friend_circle: str,
        anger_pattern: str,
        sadness_pattern: str,
        reason_for_shooting: str,
        athlete_goal: str,
    ) -> HamsaTechAthleteDetails:
        details = HamsaTechAthleteDetails(
            athlete_id=athlete_id,
            friend_circle=friend_circle,
            anger_pattern=anger_pattern,
            sadness_pattern=sadness_pattern,
            reason_for_shooting=reason_for_shooting,
            athlete_goal=athlete_goal,
        )
        self._session.add(details)
        await self._session.flush()
        return details

    async def update_step_6(
        self,
        details: HamsaTechAthleteDetails,
        *,
        friend_circle: str,
        anger_pattern: str,
        sadness_pattern: str,
        reason_for_shooting: str,
        athlete_goal: str,
    ) -> HamsaTechAthleteDetails:
        details.friend_circle = friend_circle
        details.anger_pattern = anger_pattern
        details.sadness_pattern = sadness_pattern
        details.reason_for_shooting = reason_for_shooting
        details.athlete_goal = athlete_goal
        await self._session.flush()
        return details
