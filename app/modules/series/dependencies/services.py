"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.scores.dependencies.services` — each function is a
`Depends()`-compatible provider, chained so the router ends up with a
fully-wired `SeriesService` per request without constructing anything
itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.series.repositories.session_series_repository import SessionSeriesRepository
from app.modules.series.repositories.session_series_repository_interface import (
    SeriesRepositoryInterface,
)
from app.modules.series.services.series_service import SeriesService


def get_series_repository(session: AsyncSession = Depends(get_db)) -> SeriesRepositoryInterface:
    return SessionSeriesRepository(session)


def get_series_service(
    repository: SeriesRepositoryInterface = Depends(get_series_repository),
) -> SeriesService:
    return SeriesService(repository)
