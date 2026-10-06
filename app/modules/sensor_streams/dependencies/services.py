"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.heart_rate.dependencies.services` — each function is
a `Depends()`-compatible provider, chained so the routers end up with a
fully-wired `SensorStreamService` per request without constructing
anything themselves.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.sensor_streams.repositories.sensor_stream_repository import SensorStreamRepository
from app.modules.sensor_streams.repositories.sensor_stream_repository_interface import (
    SensorStreamRepositoryInterface,
)
from app.modules.sensor_streams.services.sensor_stream_service import SensorStreamService


def get_sensor_stream_repository(session: AsyncSession = Depends(get_db)) -> SensorStreamRepositoryInterface:
    return SensorStreamRepository(session)


def get_sensor_stream_service(
    repository: SensorStreamRepositoryInterface = Depends(get_sensor_stream_repository),
) -> SensorStreamService:
    return SensorStreamService(repository)
