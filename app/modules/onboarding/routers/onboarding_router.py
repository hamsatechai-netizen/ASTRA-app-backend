"""
Onboarding router — Steps 1-6 plus completion (Batches 1 and 2).

Every endpoint requires an authenticated athlete (`get_current_athlete`)
and delegates entirely to `OnboardingService`, which reads/updates the
existing `hamsatech.athletes` row (and, for Steps 4-6, the existing
`hamsatech.athlete_details` row) matched by the authenticated identity's
phone number. Mounted under `/api/v2/onboarding` via
`app/api/v2/router.py`, giving the full paths `/api/v2/onboarding`,
`/api/v2/onboarding/step-1` through `/step-6`.

Steps 1-4's endpoints are unchanged from the previous batch; only the
GET endpoint's description was updated (as directed) to reflect that it
now also returns Steps 5-6 data and completion status, and new
`/step-5`, `/step-6` endpoints were added below `/step-4`.
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.onboarding.dependencies.services import get_onboarding_service
from app.modules.onboarding.schemas import (
    ErrorResponse,
    OnboardingStatusResponse,
    OnboardingStep1Request,
    OnboardingStep2Request,
    OnboardingStep3Request,
    OnboardingStep4Request,
    OnboardingStep5Request,
    OnboardingStep6Request,
)
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

_STEP_2_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_ONBOARDING_RESPONSES,
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "One or more Step 2 fields failed validation.",
    },
}

_STEP_3_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_ONBOARDING_RESPONSES,
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "One or more Step 3 fields failed validation.",
    },
}

_STEP_4_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_ONBOARDING_RESPONSES,
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "One or more Step 4 fields failed validation.",
    },
}

_STEP_5_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_ONBOARDING_RESPONSES,
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "One or more Step 5 fields failed validation.",
    },
}

_STEP_6_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_ONBOARDING_RESPONSES,
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "One or more Step 6 fields failed validation.",
    },
}


@router.get(
    "",
    response_model=OnboardingStatusResponse,
    responses=_ONBOARDING_RESPONSES,
    summary="Get the authenticated athlete's onboarding status",
    description=(
        "Returns the athlete ID, current onboarding step, Steps 1-6 data "
        "(whichever have already been saved), and overall completion status "
        "for the authenticated athlete."
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


@router.put(
    "/step-2",
    response_model=OnboardingStatusResponse,
    responses=_STEP_2_RESPONSES,
    summary="Save Step 2 (Athletic Background) of onboarding",
    description=(
        "Validates and saves discipline, experience level, years shooting, "
        "and academy onto the authenticated athlete's existing profile, then "
        "advances `current_onboarding_step` to 3. Never creates a new "
        "athlete record."
    ),
    tags=["Onboarding"],
)
async def save_onboarding_step_2(
    payload: OnboardingStep2Request,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingStatusResponse:
    """Save `payload` as Step 2 of onboarding for the authenticated athlete."""
    return await onboarding_service.complete_step_2(identity.phone_number, payload)


@router.put(
    "/step-3",
    response_model=OnboardingStatusResponse,
    responses=_STEP_3_RESPONSES,
    summary="Save Step 3 (Track Your Performance) of onboarding",
    description=(
        "Validates and saves average practice score, target score, "
        "performance blockers, and 30-day/6-month goals onto the "
        "authenticated athlete's existing profile, then advances "
        "`current_onboarding_step` to 4. Never creates a new athlete record."
    ),
    tags=["Onboarding"],
)
async def save_onboarding_step_3(
    payload: OnboardingStep3Request,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingStatusResponse:
    """Save `payload` as Step 3 of onboarding for the authenticated athlete."""
    return await onboarding_service.complete_step_3(identity.phone_number, payload)


@router.put(
    "/step-4",
    response_model=OnboardingStatusResponse,
    responses=_STEP_4_RESPONSES,
    summary="Save Step 4 (Academic Profile) of onboarding",
    description=(
        "Validates and saves class, school name, and academic performance "
        "onto the authenticated athlete's `athlete_details` row, creating it "
        "once if it doesn't exist yet (never duplicating it), then advances "
        "`current_onboarding_step` to 5. Never creates a new athlete record."
    ),
    tags=["Onboarding"],
)
async def save_onboarding_step_4(
    payload: OnboardingStep4Request,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingStatusResponse:
    """Save `payload` as Step 4 of onboarding for the authenticated athlete."""
    return await onboarding_service.complete_step_4(identity.phone_number, payload)


@router.put(
    "/step-5",
    response_model=OnboardingStatusResponse,
    responses=_STEP_5_RESPONSES,
    summary="Save Step 5 (Lifestyle & Wellness) of onboarding",
    description=(
        "Validates and saves diet type, outside-food frequency, sleep time, "
        "and wake time onto the authenticated athlete's `athlete_details` "
        "row, creating it once if it doesn't exist yet (never duplicating "
        "it), then advances `current_onboarding_step` to 6. Never creates a "
        "new athlete record."
    ),
    tags=["Onboarding"],
)
async def save_onboarding_step_5(
    payload: OnboardingStep5Request,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingStatusResponse:
    """Save `payload` as Step 5 of onboarding for the authenticated athlete."""
    return await onboarding_service.complete_step_5(identity.phone_number, payload)


@router.put(
    "/step-6",
    response_model=OnboardingStatusResponse,
    responses=_STEP_6_RESPONSES,
    summary="Save Step 6 (Mental & Social Profile) of onboarding — final step",
    description=(
        "Validates and saves friend circle, anger pattern, sadness pattern, "
        "reason for shooting, and athlete goal onto the authenticated "
        "athlete's `athlete_details` row, creating it once if it doesn't "
        "exist yet (never duplicating it). This is the final onboarding "
        "step: `current_onboarding_step` is set to 6 (it does not advance "
        "further) and `is_onboarding_complete` becomes `true`. Never "
        "creates a new athlete record."
    ),
    tags=["Onboarding"],
)
async def save_onboarding_step_6(
    payload: OnboardingStep6Request,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingStatusResponse:
    """Save `payload` as Step 6 of onboarding for the authenticated athlete."""
    return await onboarding_service.complete_step_6(identity.phone_number, payload)
