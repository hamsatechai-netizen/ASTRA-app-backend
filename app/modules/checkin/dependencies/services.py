"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.series.dependencies.services` — each function is a
`Depends()`-compatible provider, chained so the router ends up with a
fully-wired `CheckinService` per request without constructing anything
itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.checkin.repositories.checkin_repository import CheckinRepository
from app.modules.checkin.repositories.checkin_repository_interface import CheckinRepositoryInterface
from app.modules.checkin.services.checkin_service import CheckinService


def get_checkin_repository(session: AsyncSession = Depends(get_db)) -> CheckinRepositoryInterface:
    return CheckinRepository(session)


def get_checkin_service(
    repository: CheckinRepositoryInterface = Depends(get_checkin_repository),
) -> CheckinService:
    return CheckinService(repository)
