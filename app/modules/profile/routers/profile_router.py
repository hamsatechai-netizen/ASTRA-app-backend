"""
Profile router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `ProfileService`. Mounted under `/api/mobile` (not `/api/v2`)
via `app/api/mobile/router.py`, matching the path the Flutter client
already calls: `GET`/`PUT /api/mobile/athletes/{athlete_id}/profile`
(`lib/core/services/api_service.dart:995-1031`).

Like `sessions`/`scores`/`series`/`reflections`, this endpoint's URL
carries `athlete_id` — `ProfileService` verifies it matches the
authenticated identity's own athlete profile before reading or writing
anything.
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.profile.dependencies.services import get_profile_service
from app.modules.profile.schemas import ErrorResponse, ProfileResponse, UpdateProfileRequest
from app.modules.profile.services.profile_service import ProfileService

router = APIRouter()

_PROFILE_RESPONSES: dict[int | str, dict[str, Any]] = {
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
    "/athletes/{athlete_id}/profile",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    responses=_PROFILE_RESPONSES,
    summary="Fetch the authenticated athlete's profile",
    tags=["Profile"],
)
async def get_profile(
    athlete_id: str,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    profile_service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    """Return `athlete_id`'s profile, if it belongs to the caller."""
    return await profile_service.get_profile(identity.phone_number, athlete_id)


@router.put(
    "/athletes/{athlete_id}/profile",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    responses=_PROFILE_RESPONSES,
    summary="Update the authenticated athlete's editable profile fields",
    tags=["Profile"],
)
async def update_profile(
    athlete_id: str,
    payload: UpdateProfileRequest,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    profile_service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    """Apply only the fields present in `payload` to `athlete_id`'s profile, if it belongs to the caller."""
    return await profile_service.update_profile(identity.phone_number, athlete_id, payload)
