"""
Onboarding router — Step 1 (Personal Details) only.

Both endpoints require an authenticated athlete (`get_current_athlete`)
and delegate entirely to `OnboardingService`, which reads/updates the
existing `hamsatech.athletes` row matched by the authenticated identity's
phone number. Mounted under `/api/v2/onboarding` via
`app/api/v2/router.py`, giving the full paths `/api/v2/onboarding` and
`/api/v2/onboarding/step-1`.
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.onboarding.dependencies.services import get_onboarding_service
from app.modules.onboarding.schemas import ErrorResponse, OnboardingStatusResponse, OnboardingStep1Request
from app.modules.onboarding.services.onboarding_service import OnboardingService

router = APIRouter()

_ONBOARDING_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "Missing, invalid, or expired access token.",
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "No athlete profile exists for the authenticated account.",
    },
}

_STEP_1_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_ONBOARDING_RESPONSES,
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "One or more Step 1 fields failed validation.",
    },
}


@router.get(
    "",
    response_model=OnboardingStatusResponse,
    responses=_ONBOARDING_RESPONSES,
    summary="Get the authenticated athlete's onboarding status",
    description=(
        "Returns the athlete ID, current onboarding step, Step 1 personal "
        "details (if already saved), and overall completion status for the "
        "authenticated athlete."
    ),
    tags=["Onboarding"],
)
async def get_onboarding_status(
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingStatusResponse:
    """Return the current onboarding state for the authenticated athlete."""
    return await onboarding_service.get_status(identity.phone_number)


@router.put(
    "/step-1",
    response_model=OnboardingStatusResponse,
    responses=_STEP_1_RESPONSES,
    summary="Save Step 1 (Personal Details) of onboarding",
    description=(
        "Validates and saves full name, date of birth, gender, and city onto "
        "the authenticated athlete's existing profile, then advances "
        "`current_onboarding_step` to 2. Never creates a new athlete record."
    ),
    tags=["Onboarding"],
)
async def save_onboarding_step_1(
    payload: OnboardingStep1Request,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingStatusResponse:
    """Save `payload` as Step 1 of onboarding for the authenticated athlete."""
    return await onboarding_service.complete_step_1(identity.phone_number, payload)
