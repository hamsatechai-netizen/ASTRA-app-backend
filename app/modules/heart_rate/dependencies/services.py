"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.psychology_assessment.dependencies.services` — each
function is a `Depends()`-compatible provider, chained so the router ends
up with a fully-wired `HeartRateService` per request without constructing
anything itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.heart_rate.repositories.hr_stream_repository import HrStreamRepository
from app.modules.heart_rate.repositories.hr_stream_repository_interface import HrStreamRepositoryInterface
from app.modules.heart_rate.services.heart_rate_service import HeartRateService


def get_hr_stream_repository(session: AsyncSession = Depends(get_db)) -> HrStreamRepositoryInterface:
    return HrStreamRepository(session)


def get_heart_rate_service(
    repository: HrStreamRepositoryInterface = Depends(get_hr_stream_repository),
) -> HeartRateService:
    return HeartRateService(repository)
