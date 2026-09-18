"""
Streak router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `StreakService`. Mounted under `/api/mobile` via
`app/api/mobile/router.py`, matching the path shape every other
`/api/mobile/athletes/{athlete_id}/...` endpoint already uses.
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.streak.dependencies.services import get_streak_service
from app.modules.streak.schemas import ErrorResponse, StreakResponse
from app.modules.streak.services.streak_service import StreakService

router = APIRouter()

_STREAK_RESPONSES: dict[int | str, dict[str, Any]] = {
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


@router.get(
    "/athletes/{athlete_id}/streak",
    response_model=StreakResponse,
    status_code=status.HTTP_200_OK,
    responses=_STREAK_RESPONSES,
    summary="Fetch the authenticated athlete's current and longest training streak",
    tags=["Streak"],
)
async def get_streak(
    athlete_id: str,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    streak_service: StreakService = Depends(get_streak_service),
) -> StreakResponse:
    """Return `athlete_id`'s current/longest streak, if it belongs to the caller."""
    return await streak_service.get_streak(identity.phone_number, athlete_id)
