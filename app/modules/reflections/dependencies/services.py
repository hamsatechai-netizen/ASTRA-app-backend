"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.scores.dependencies.services` — each function is a
`Depends()`-compatible provider, chained so the router ends up with a
fully-wired `ReflectionService` per request without constructing anything
itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.reflections.repositories.session_post_log_repository import (
    SessionPostLogRepository,
)
from app.modules.reflections.repositories.session_post_log_repository_interface import (
    ReflectionRepositoryInterface,
)
from app.modules.reflections.services.reflection_service import ReflectionService


def get_reflection_repository(session: AsyncSession = Depends(get_db)) -> ReflectionRepositoryInterface:
    return SessionPostLogRepository(session)


def get_reflection_service(
    repository: ReflectionRepositoryInterface = Depends(get_reflection_repository),
) -> ReflectionService:
    return ReflectionService(repository)
