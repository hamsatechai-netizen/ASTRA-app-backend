"""
Sessions router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `SessionService`. Mounted under `/api/mobile` (not `/api/v2`)
via `app/api/mobile/router.py`, matching the path the Flutter client
already calls: `POST /api/mobile/athletes/{athlete_id}/sessions`.

Unlike v2 endpoints (which never take an athlete ID from the client), this
endpoint's URL carries `athlete_id` — `SessionService` verifies it matches
the authenticated identity's own athlete profile before creating anything.
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.sessions.dependencies.services import get_session_service
from app.modules.sessions.schemas import CreateSessionRequest, ErrorResponse, SessionResponse
from app.modules.sessions.services.session_service import SessionService

router = APIRouter()

_SESSION_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "Missing, invalid, or expired access token.",
    },
    status.HTTP_403_FORBIDDEN: {
        "model": ErrorResponse,
        "description": "The athlete_id in the path does not belong to the authenticated account.",
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "No athlete profile exists for the authenticated account.",
    },
}


@router.post(
    "/athletes/{athlete_id}/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_SESSION_RESPONSES,
    summary="Create a new training session for the authenticated athlete",
    tags=["Sessions"],
)
async def create_session(
    athlete_id: str,
    payload: CreateSessionRequest,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    session_service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Create and return a new training session for `athlete_id`, if it belongs to the caller."""
    return await session_service.create_session(identity.phone_number, athlete_id, payload)
