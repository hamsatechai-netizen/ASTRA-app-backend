"""
Session HR read-back router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `HeartRateService.get_session_hr`. Mounted under `/api/mobile`
(not `/api/v2/heart-rate`) via `app/api/mobile/router.py`, matching the
same `/athletes/{athlete_id}/sessions/{session_id}/...` path shape the
`sessions` module already uses for `complete_session` — kept as its own
router/file rather than added to `heart_rate_router.py` so the existing
`/api/v2/heart-rate/samples` write-only router's mount point is untouched.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.heart_rate.dependencies.services import get_heart_rate_service
from app.modules.heart_rate.schemas import ErrorResponse, SessionHrResponse
from app.modules.heart_rate.services.heart_rate_service import HeartRateService

router = APIRouter()

_SESSION_HR_RESPONSES: dict[int | str, dict[str, Any]] = {
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
    "/athletes/{athlete_id}/sessions/{session_id}/heart-rate",
    response_model=SessionHrResponse,
    status_code=status.HTTP_200_OK,
    responses=_SESSION_HR_RESPONSES,
    summary="Get aggregated HR data for a training session",
    tags=["Heart Rate"],
)
async def get_session_heart_rate(
    athlete_id: str,
    session_id: UUID,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    heart_rate_service: HeartRateService = Depends(get_heart_rate_service),
) -> SessionHrResponse:
    """Return aggregated, chart-ready HR data for `session_id`, if it belongs to the caller."""
    return await heart_rate_service.get_session_hr(identity.phone_number, athlete_id, session_id)
