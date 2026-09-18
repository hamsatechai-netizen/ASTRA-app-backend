"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.profile.dependencies.services` — each function is a
`Depends()`-compatible provider, chained so the router ends up with a
fully-wired `DashboardService` per request without constructing anything
itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.dashboard.repositories.dashboard_repository import DashboardRepository
from app.modules.dashboard.repositories.dashboard_repository_interface import (
    DashboardRepositoryInterface,
)
from app.modules.dashboard.services.dashboard_service import DashboardService


def get_dashboard_repository(session: AsyncSession = Depends(get_db)) -> DashboardRepositoryInterface:
    return DashboardRepository(session)


def get_dashboard_service(
    repository: DashboardRepositoryInterface = Depends(get_dashboard_repository),
) -> DashboardService:
    return DashboardService(repository)
