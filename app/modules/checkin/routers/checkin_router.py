"""
Daily check-in router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `CheckinService`. Mounted under `/api/v1` via
`app/api/v1/router.py`, at the existing, already-active Flutter path:
`POST /api/v1/checkin/daily` (`lib/core/services/api_service.dart:155-173`).

Unlike the `/api/mobile/athletes/{athlete_id}/...` modules, `athlete_id`
here comes from the request body (the existing Flutter contract already
sends it there, not in the URL) — `CheckinService` verifies it matches
the authenticated identity's own athlete profile before writing anything.
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.checkin.dependencies.services import get_checkin_service
from app.modules.checkin.schemas import CheckinResponse, ErrorResponse, SaveCheckinRequest
from app.modules.checkin.services.checkin_service import CheckinService

router = APIRouter()

_CHECKIN_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "Missing, invalid, or expired access token.",
    },
    status.HTTP_403_FORBIDDEN: {
        "model": ErrorResponse,
        "description": "The athlete_id in the request body does not belong to the authenticated account.",
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "No athlete profile exists for the authenticated account.",
    },
}


@router.post(
    "/checkin/daily",
    response_model=CheckinResponse,
    status_code=status.HTTP_200_OK,
    responses=_CHECKIN_RESPONSES,
    summary="Save (or update) the authenticated athlete's check-in for the current UTC day",
    tags=["Daily Check-in"],
)
async def save_daily_checkin(
    payload: SaveCheckinRequest,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    checkin_service: CheckinService = Depends(get_checkin_service),
) -> CheckinResponse:
    """Upsert today's (UTC) check-in for the caller, if `payload.athlete_id` matches their own profile."""
    return await checkin_service.save_checkin(identity.phone_number, payload)
