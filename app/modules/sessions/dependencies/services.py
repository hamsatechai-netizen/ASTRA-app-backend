"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.heart_rate.dependencies.services` — each function is
a `Depends()`-compatible provider, chained so the router ends up with a
fully-wired `SessionService` per request without constructing anything
itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.sessions.repositories.session_repository import SessionRepository
from app.modules.sessions.repositories.session_repository_interface import SessionRepositoryInterface
from app.modules.sessions.services.session_service import SessionService


def get_session_repository(session: AsyncSession = Depends(get_db)) -> SessionRepositoryInterface:
    return SessionRepository(session)


def get_session_service(
    repository: SessionRepositoryInterface = Depends(get_session_repository),
) -> SessionService:
    return SessionService(repository)
