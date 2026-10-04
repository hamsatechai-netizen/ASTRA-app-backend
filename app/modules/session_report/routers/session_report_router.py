"""
Session report router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `SessionReportService`. Mounted under `/api/mobile` via
`app/api/mobile/router.py`, matching the same
`/athletes/{athlete_id}/sessions/{session_id}/...` path shape the
`sessions`, `heart_rate`, `scores`, `series`, and `reflections` modules
already use.

Read-only: this router never writes to any table. It aggregates data
already persisted through the existing session, heart-rate, score,
series, and reflection endpoints.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.session_report.dependencies.services import get_session_report_service
from app.modules.session_report.schemas import ErrorResponse, SessionReportResponse
from app.modules.session_report.services.session_report_service import SessionReportService

router = APIRouter()

_SESSION_REPORT_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "Missing, invalid, or expired access token.",
    },
    status.HTTP_403_FORBIDDEN: {
        "model": ErrorResponse,
        "description": "The athlete_id in the path, or the session, does not belong to the "
        "authenticated account.",
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "No athlete profile exists for the authenticated account, or no session "
        "exists for session_id.",
    },
}


@router.get(
    "/athletes/{athlete_id}/sessions/{session_id}/report",
    response_model=SessionReportResponse,
    status_code=status.HTTP_200_OK,
    responses=_SESSION_REPORT_RESPONSES,
    summary="Get the full report for a training session",
    tags=["Session Report"],
)
async def get_session_report(
    athlete_id: str,
    session_id: UUID,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    session_report_service: SessionReportService = Depends(get_session_report_service),
) -> SessionReportResponse:
    """Return the aggregated report for `session_id`, if it belongs to the caller."""
    return await session_report_service.get_session_report(identity.phone_number, athlete_id, session_id)
