"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.sessions.dependencies.services` — each function is a
`Depends()`-compatible provider, chained so the router ends up with a
fully-wired `ProfileService` per request without constructing anything
itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.profile.repositories.profile_repository import ProfileRepository
from app.modules.profile.repositories.profile_repository_interface import ProfileRepositoryInterface
from app.modules.profile.services.profile_service import ProfileService


def get_profile_repository(session: AsyncSession = Depends(get_db)) -> ProfileRepositoryInterface:
    return ProfileRepository(session)


def get_profile_service(
    repository: ProfileRepositoryInterface = Depends(get_profile_repository),
) -> ProfileService:
    return ProfileService(repository)
