"""
Dashboard router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `DashboardService`. Mounted under `/api/mobile` (not `/api/v2`)
via `app/api/mobile/router.py`, matching the path the Flutter client
already calls: `GET /api/mobile/athletes/{athlete_id}/home`
(`lib/core/services/api_service.dart:1114-1117`).

Like `sessions`/`scores`/`profile`, this endpoint's URL carries
`athlete_id` — `DashboardService` verifies it matches the authenticated
identity's own athlete profile before reading anything.
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.dashboard.dependencies.services import get_dashboard_service
from app.modules.dashboard.schemas import DashboardHomeResponse, ErrorResponse
from app.modules.dashboard.services.dashboard_service import DashboardService

router = APIRouter()

_HOME_RESPONSES: dict[int | str, dict[str, Any]] = {
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
    "/athletes/{athlete_id}/home",
    response_model=DashboardHomeResponse,
    status_code=status.HTTP_200_OK,
    responses=_HOME_RESPONSES,
    summary="Fetch the authenticated athlete's dashboard home summary",
    tags=["Dashboard"],
)
async def get_home(
    athlete_id: str,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    dashboard_service: DashboardService = Depends(get_dashboard_service),
) -> DashboardHomeResponse:
    """Return `athlete_id`'s dashboard home summary, if it belongs to the caller."""
    return await dashboard_service.get_home(identity.phone_number, athlete_id)
