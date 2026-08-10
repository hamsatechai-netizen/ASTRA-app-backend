"""
Heart-rate router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `HeartRateService`, which resolves the athlete server-side
from the token and writes the given batch into the existing
`hamsatech.hr_stream` table. Mounted under `/api/v2/heart-rate` via
`app/api/v2/router.py`.

Write-only by design: no GET endpoint exists on this router.
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.heart_rate.dependencies.services import get_heart_rate_service
from app.modules.heart_rate.schemas import ErrorResponse, HrSampleBatchRequest, HrSampleBatchResponse
from app.modules.heart_rate.services.heart_rate_service import HeartRateService

router = APIRouter()

_SAMPLES_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "Missing, invalid, or expired access token.",
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "No athlete profile exists for the authenticated account.",
    },
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "The batch is empty/too large, or a sample failed validation.",
    },
}


@router.post(
    "/samples",
    response_model=HrSampleBatchResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_SAMPLES_RESPONSES,
    summary="Store a batch of HR samples",
    description=(
        "Inserts every sample in the batch into `hamsatech.hr_stream` for "
        "the authenticated athlete, resolved server-side from the access "
        "token — the request body never carries an athlete ID."
    ),
    tags=["Heart Rate"],
)
async def record_hr_samples(
    payload: HrSampleBatchRequest,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    heart_rate_service: HeartRateService = Depends(get_heart_rate_service),
) -> HrSampleBatchResponse:
    """Store `payload`'s HR samples for the authenticated athlete."""
    return await heart_rate_service.record_samples(identity.phone_number, payload)
