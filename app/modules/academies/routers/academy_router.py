"""
Academies router — read-only academy listing for onboarding Step 2.

Requires an authenticated athlete (`get_current_athlete`, the same
dependency the onboarding module uses) and delegates entirely to
`AcademyService`. Mounted under `/api/v2/academies` via
`app/api/v2/router.py`, giving the full path `GET /api/v2/academies`.
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.modules.academies.dependencies.services import get_academy_service
from app.modules.academies.schemas import AcademyResponse, ErrorResponse
from app.modules.academies.services.academy_service import AcademyService
from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity

router = APIRouter()

_ACADEMIES_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "Missing, invalid, or expired access token.",
    },
}


@router.get(
    "",
    response_model=list[AcademyResponse],
    responses=_ACADEMIES_RESPONSES,
    summary="List academies",
    description=(
        "Returns every academy for the authenticated athlete to choose from "
        "during onboarding Step 2. Returns an empty list if none exist — "
        "never a 404."
    ),
    tags=["Academies"],
)
async def list_academies(
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    academy_service: AcademyService = Depends(get_academy_service),
) -> list[AcademyResponse]:
    """Return every academy for the authenticated athlete."""
    return await academy_service.list_academies()
