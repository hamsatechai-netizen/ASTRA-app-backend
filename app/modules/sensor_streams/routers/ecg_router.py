"""
ECG sample ingestion router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `SensorStreamService`, which resolves the athlete server-side
from the token, verifies the batch's session belongs to them, and
bulk-inserts the batch into the existing `hamsatech.ecg_stream` table.
Mounted under `/api/v2/ecg` via `app/api/v2/router.py`.

Write-only by design: no GET endpoint exists on this router.
"""

from fastapi import APIRouter, Depends, Request, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.sensor_streams.dependencies.body import batch_body
from app.modules.sensor_streams.dependencies.services import get_sensor_stream_service
from app.modules.sensor_streams.routers.common import (
    PER_CALLER_LIMIT,
    PER_IP_LIMIT,
    SAMPLES_RESPONSES,
    request_body_openapi,
)
from app.modules.sensor_streams.schemas import EcgSampleBatchRequest, SensorSampleBatchResponse
from app.modules.sensor_streams.services.sensor_stream_service import SensorStreamService
from app.security.rate_limiter import authenticated_caller_key, limiter

router = APIRouter()


@router.post(
    "/samples",
    response_model=SensorSampleBatchResponse,
    status_code=status.HTTP_201_CREATED,
    responses=SAMPLES_RESPONSES,
    summary="Store a batch of ECG samples",
    description=(
        "Bulk-inserts every sample in the batch into `hamsatech.ecg_stream` for the "
        "authenticated athlete, resolved server-side from the access token — the request "
        "body never carries an athlete ID. The session must belong to that athlete. "
        "`ecgValue` is in microvolts; `recordedAt` must carry a UTC offset. "
        "Idempotent: `batchId` identifies the batch, so retrying with the same `batchId` never "
        "stores its samples twice and returns the original accepted count."
    ),
    tags=["ECG"],
    openapi_extra=request_body_openapi(EcgSampleBatchRequest),
)
@limiter.limit(PER_CALLER_LIMIT, key_func=authenticated_caller_key)
@limiter.limit(PER_IP_LIMIT)
async def record_ecg_samples(
    request: Request,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    payload: EcgSampleBatchRequest = Depends(batch_body(EcgSampleBatchRequest)),
    service: SensorStreamService = Depends(get_sensor_stream_service),
) -> SensorSampleBatchResponse:
    """Store `payload`'s ECG samples for the authenticated athlete's own session."""
    return await service.record_ecg_samples(identity.phone_number, payload)
