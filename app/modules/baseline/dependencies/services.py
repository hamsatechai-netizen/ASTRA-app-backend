"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.streak.dependencies.services` — each function is a
`Depends()`-compatible provider, chained so the router ends up with a
fully-wired `BaselineService` per request without constructing anything
itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.baseline.repositories.baseline_repository import BaselineRepository
from app.modules.baseline.repositories.baseline_repository_interface import BaselineRepositoryInterface
from app.modules.baseline.services.baseline_service import BaselineService


def get_baseline_repository(session: AsyncSession = Depends(get_db)) -> BaselineRepositoryInterface:
    return BaselineRepository(session)


def get_baseline_service(
    repository: BaselineRepositoryInterface = Depends(get_baseline_repository),
) -> BaselineService:
    return BaselineService(repository)
