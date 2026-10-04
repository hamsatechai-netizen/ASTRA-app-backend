"""
Concrete onboarding-profile repository (SQLAlchemy) against the existing
`hamsatech.athletes` table. Only ever flushes, never commits — the
request-scoped `AsyncSession` from `app.dependencies.database.get_db`
owns the transaction boundary.
"""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.onboarding.repositories.onboarding_repository_interface import (
    OnboardingRepositoryInterface,
)

_STEP_2 = 2
_STEP_3 = 3
_STEP_4 = 4


class OnboardingRepository(OnboardingRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def save_step_1(
        self,
        athlete: HamsaTechAthlete,
        *,
        full_name: str,
        date_of_birth: date,
        gender: str,
        city: str,
    ) -> HamsaTechAthlete:
        athlete.athlete_name = full_name
        athlete.date_of_birth = date_of_birth
        athlete.gender = gender
        athlete.city = city
        athlete.current_onboarding_step = _STEP_2
        await self._session.flush()
        return athlete

    async def save_step_2(
        self,
        athlete: HamsaTechAthlete,
        *,
        discipline: str,
        experience_level: str,
        years_shooting: int,
        academy_id: UUID,
    ) -> HamsaTechAthlete:
        athlete.weapon_specialization = discipline
        athlete.experience_level = experience_level
        athlete.years_shooting = years_shooting
        athlete.academy_id = academy_id
        athlete.current_onboarding_step = _STEP_3
        await self._session.flush()
        return athlete

    async def save_step_3(
        self,
        athlete: HamsaTechAthlete,
        *,
        average_practice_score: float,
        target_score: float,
        performance_blockers: list[str],
        goal_30_day: str,
        goal_6_month: str,
    ) -> HamsaTechAthlete:
        athlete.avg_practice_score = average_practice_score
        athlete.target_score = target_score
        athlete.performance_blockers = performance_blockers
        athlete.goal_30_day = goal_30_day
        athlete.goal_6_month = goal_6_month
        athlete.current_onboarding_step = _STEP_4
        await self._session.flush()
        return athlete

    async def advance_onboarding_step(self, athlete: HamsaTechAthlete, step: int) -> HamsaTechAthlete:
        athlete.current_onboarding_step = step
        await self._session.flush()
        return athlete
