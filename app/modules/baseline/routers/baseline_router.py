"""
Baseline router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `BaselineService`. Mounted under `/api/mobile` via
`app/api/mobile/router.py`, matching the path shape every other
`/api/mobile/athletes/{athlete_id}/...` endpoint already uses — and the
exact path the existing Flutter client already calls for
`saveBaselineHR` (`lib/core/services/api_service.dart:1038-1047`).
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.baseline.dependencies.services import get_baseline_service
from app.modules.baseline.schemas import BaselineResponse, ErrorResponse, SaveBaselineRequest
from app.modules.baseline.services.baseline_service import BaselineService

router = APIRouter()

_BASELINE_RESPONSES: dict[int | str, dict[str, Any]] = {
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
    "/athletes/{athlete_id}/baseline",
    response_model=BaselineResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        **_BASELINE_RESPONSES,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ErrorResponse,
            "description": "resting_hr failed validation (must be > 0 and <= 300).",
        },
    },
    summary="Capture a new physiological baseline (resting heart rate) for the authenticated athlete",
    tags=["Baseline"],
)
async def create_baseline(
    athlete_id: str,
    payload: SaveBaselineRequest,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    baseline_service: BaselineService = Depends(get_baseline_service),
) -> BaselineResponse:
    """Insert a new baseline row for `athlete_id`, if it belongs to the caller."""
    return await baseline_service.create_baseline(identity.phone_number, athlete_id, payload.resting_hr)


@router.get(
    "/athletes/{athlete_id}/baseline",
    response_model=BaselineResponse,
    status_code=status.HTTP_200_OK,
    responses={
        **_BASELINE_RESPONSES,
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No athlete profile exists for the authenticated account, or no baseline "
            "has been captured yet.",
        },
    },
    summary="Fetch the authenticated athlete's most recently captured baseline",
    tags=["Baseline"],
)
async def get_baseline(
    athlete_id: str,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    baseline_service: BaselineService = Depends(get_baseline_service),
) -> BaselineResponse:
    """Return `athlete_id`'s most recently captured baseline, if it belongs to the caller."""
    return await baseline_service.get_latest_baseline(identity.phone_number, athlete_id)
