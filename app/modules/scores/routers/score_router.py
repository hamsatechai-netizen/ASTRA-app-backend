"""
Score router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `ScoreService`. Mounted under `/api/mobile` via
`app/api/mobile/router.py`, matching the same
`/athletes/{athlete_id}/sessions/{session_id}/...` path shape the
`sessions` and `heart_rate` modules already use.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.scores.dependencies.services import get_score_service
from app.modules.scores.schemas import ErrorResponse, SaveScoreRequest, ScoreResponse
from app.modules.scores.services.score_service import ScoreService

router = APIRouter()

_SCORE_RESPONSES: dict[int | str, dict[str, Any]] = {
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
    "/athletes/{athlete_id}/sessions/{session_id}/score",
    response_model=ScoreResponse,
    status_code=status.HTTP_200_OK,
    responses=_SCORE_RESPONSES,
    summary="Save (or update) a training session's score summary",
    tags=["Scores"],
)
async def save_score(
    athlete_id: str,
    session_id: UUID,
    payload: SaveScoreRequest,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    score_service: ScoreService = Depends(get_score_service),
) -> ScoreResponse:
    """Upsert `session_id`'s score summary, if it belongs to `athlete_id` and to the caller."""
    return await score_service.save_score(identity.phone_number, athlete_id, session_id, payload)
