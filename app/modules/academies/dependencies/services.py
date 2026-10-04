"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.onboarding.dependencies.services` — each function is
a `Depends()`-compatible provider, chained so the router ends up with a
fully-wired `AcademyService` per request without constructing anything
itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.academies.repositories.academy_repository import AcademyRepository
from app.modules.academies.repositories.academy_repository_interface import AcademyRepositoryInterface
from app.modules.academies.services.academy_service import AcademyService


def get_academy_repository(session: AsyncSession = Depends(get_db)) -> AcademyRepositoryInterface:
    return AcademyRepository(session)


def get_academy_service(
    repository: AcademyRepositoryInterface = Depends(get_academy_repository),
) -> AcademyService:
    return AcademyService(repository)
