"""
Concrete profile repository (SQLAlchemy) against the existing
`hamsatech.athletes` table. Only ever flushes, never commits — the
request-scoped `AsyncSession` from `app.dependencies.database.get_db`
owns the transaction boundary (same convention as every other module's
repository, e.g. `app.modules.sessions.repositories.session_repository`).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.profile.repositories.profile_repository_interface import ProfileRepositoryInterface


class ProfileRepository(ProfileRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def update_fields(
        self,
        athlete: HamsaTechAthlete,
        *,
        athlete_name: str | None = None,
        weapon_specialization: str | None = None,
        experience_level: str | None = None,
        goal_30_day: str | None = None,
        goal_6_month: str | None = None,
    ) -> HamsaTechAthlete:
        if athlete_name is not None:
            athlete.athlete_name = athlete_name
        if weapon_specialization is not None:
            athlete.weapon_specialization = weapon_specialization
        if experience_level is not None:
            athlete.experience_level = experience_level
        if goal_30_day is not None:
            athlete.goal_30_day = goal_30_day
        if goal_6_month is not None:
            athlete.goal_6_month = goal_6_month

        await self._session.flush()
        return athlete
