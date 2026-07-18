"""
Concrete onboarding-profile repository (SQLAlchemy) against the existing
`hamsatech.athletes` table. Only ever flushes, never commits — the
request-scoped `AsyncSession` from `app.dependencies.database.get_db`
owns the transaction boundary.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.onboarding.repositories.onboarding_repository_interface import (
    OnboardingRepositoryInterface,
)

_STEP_2 = 2


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
