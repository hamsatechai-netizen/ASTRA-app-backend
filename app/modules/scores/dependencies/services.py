"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.sessions.dependencies.services` — each function is a
`Depends()`-compatible provider, chained so the router ends up with a
fully-wired `ScoreService` per request without constructing anything
itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.scores.repositories.shooting_session_log_repository import (
    ShootingSessionLogRepository,
)
from app.modules.scores.repositories.shooting_session_log_repository_interface import (
    ScoreRepositoryInterface,
)
from app.modules.scores.services.score_service import ScoreService


def get_score_repository(session: AsyncSession = Depends(get_db)) -> ScoreRepositoryInterface:
    return ShootingSessionLogRepository(session)


def get_score_service(
    repository: ScoreRepositoryInterface = Depends(get_score_repository),
) -> ScoreService:
    return ScoreService(repository)
