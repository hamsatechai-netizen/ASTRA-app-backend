"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.auth.dependencies.services` — each function is a
`Depends()`-compatible provider, chained so the router ends up with a
fully-wired `OnboardingService` per request without constructing
anything itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.onboarding.repositories.athlete_details_repository import AthleteDetailsRepository
from app.modules.onboarding.repositories.athlete_details_repository_interface import (
    AthleteDetailsRepositoryInterface,
)
from app.modules.onboarding.repositories.onboarding_repository import OnboardingRepository
from app.modules.onboarding.repositories.onboarding_repository_interface import (
    OnboardingRepositoryInterface,
)
from app.modules.onboarding.services.onboarding_service import OnboardingService


def get_onboarding_repository(session: AsyncSession = Depends(get_db)) -> OnboardingRepositoryInterface:
    return OnboardingRepository(session)


def get_athlete_details_repository(
    session: AsyncSession = Depends(get_db),
) -> AthleteDetailsRepositoryInterface:
    return AthleteDetailsRepository(session)


def get_onboarding_service(
    repository: OnboardingRepositoryInterface = Depends(get_onboarding_repository),
    athlete_details_repository: AthleteDetailsRepositoryInterface = Depends(get_athlete_details_repository),
) -> OnboardingService:
    return OnboardingService(repository, athlete_details_repository)
