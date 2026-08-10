"""
Concrete academy repository (SQLAlchemy) against the existing
`hamsatech.academies` table. Read-only — no writes are ever issued.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_academy import HamsaTechAcademy
from app.modules.academies.repositories.academy_repository_interface import AcademyRepositoryInterface


class AcademyRepository(AcademyRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> list[HamsaTechAcademy]:
        result = await self._session.execute(select(HamsaTechAcademy).order_by(HamsaTechAcademy.academy_name))
        return list(result.scalars().all())
