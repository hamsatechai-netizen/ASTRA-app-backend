"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.dashboard.dependencies.services` — each function is a
`Depends()`-compatible provider, chained so the router ends up with a
fully-wired `StreakService` per request without constructing anything
itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.streak.repositories.streak_repository import StreakRepository
from app.modules.streak.repositories.streak_repository_interface import StreakRepositoryInterface
from app.modules.streak.services.streak_service import StreakService


def get_streak_repository(session: AsyncSession = Depends(get_db)) -> StreakRepositoryInterface:
    return StreakRepository(session)


def get_streak_service(
    repository: StreakRepositoryInterface = Depends(get_streak_repository),
) -> StreakService:
    return StreakService(repository)
