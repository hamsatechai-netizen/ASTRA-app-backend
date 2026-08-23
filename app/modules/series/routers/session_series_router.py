"""
Session series router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `SeriesService`. Mounted under `/api/mobile` via
`app/api/mobile/router.py`, matching the same
`/athletes/{athlete_id}/sessions/{session_id}/...` path shape the
`sessions`, `heart_rate`, `scores`, and `reflections` modules already
use — and the exact path `ScoreEntryBloc._syncSeries` already calls.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.series.dependencies.services import get_series_service
from app.modules.series.schemas import ErrorResponse, SaveSeriesRequest, SeriesResponse
from app.modules.series.services.series_service import SeriesService

router = APIRouter()

_SERIES_RESPONSES: dict[int | str, dict[str, Any]] = {
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


@router.post(
    "/athletes/{athlete_id}/sessions/{session_id}/series",
    response_model=SeriesResponse,
    status_code=status.HTTP_200_OK,
    responses=_SERIES_RESPONSES,
    summary="Save (or update) one completed series within a training session",
    tags=["Series"],
)
async def save_series(
    athlete_id: str,
    session_id: UUID,
    payload: SaveSeriesRequest,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    series_service: SeriesService = Depends(get_series_service),
) -> SeriesResponse:
    """Upsert one series for `session_id`, if it belongs to `athlete_id` and to the caller."""
    return await series_service.save_series(identity.phone_number, athlete_id, session_id, payload)
