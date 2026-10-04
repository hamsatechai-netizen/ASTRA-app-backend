"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.heart_rate.dependencies.services` — each function is
a `Depends()`-compatible provider, chained so the router ends up with a
fully-wired `SessionReportService` per request without constructing
anything itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.session_report.repositories.session_report_repository import SessionReportRepository
from app.modules.session_report.repositories.session_report_repository_interface import (
    SessionReportRepositoryInterface,
)
from app.modules.session_report.services.session_report_service import SessionReportService


def get_session_report_repository(
    session: AsyncSession = Depends(get_db),
) -> SessionReportRepositoryInterface:
    return SessionReportRepository(session)


def get_session_report_service(
    repository: SessionReportRepositoryInterface = Depends(get_session_report_repository),
) -> SessionReportService:
    return SessionReportService(repository)
