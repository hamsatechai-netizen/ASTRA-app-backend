"""
Session reflection router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `ReflectionService`. Mounted under `/api/mobile` via
`app/api/mobile/router.py`, matching the same
`/athletes/{athlete_id}/sessions/{session_id}/...` path shape the
`sessions`, `heart_rate`, and `scores` modules already use.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.reflections.dependencies.services import get_reflection_service
from app.modules.reflections.schemas import ErrorResponse, ReflectionResponse, SaveReflectionRequest
from app.modules.reflections.services.reflection_service import ReflectionService

router = APIRouter()

_REFLECTION_RESPONSES: dict[int | str, dict[str, Any]] = {
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
    "/athletes/{athlete_id}/sessions/{session_id}/reflection",
    response_model=ReflectionResponse,
    status_code=status.HTTP_200_OK,
    responses=_REFLECTION_RESPONSES,
    summary="Save (or update) a training session's reflection",
    tags=["Reflections"],
)
async def save_reflection(
    athlete_id: str,
    session_id: UUID,
    payload: SaveReflectionRequest = SaveReflectionRequest(),
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    reflection_service: ReflectionService = Depends(get_reflection_service),
) -> ReflectionResponse:
    """Upsert `session_id`'s reflection, if it belongs to `athlete_id` and to the caller."""
    return await reflection_service.save_reflection(identity.phone_number, athlete_id, session_id, payload)
