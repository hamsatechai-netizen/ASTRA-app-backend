"""
Accelerometer (ACC) sample ingestion router.

Requires an authenticated athlete (`get_current_athlete`) and delegates
entirely to `SensorStreamService`, which resolves the athlete server-side
from the token, verifies the batch's session belongs to them, and
bulk-inserts the batch into the existing `hamsatech.acc_stream` table.
Mounted under `/api/v2/acc` via `app/api/v2/router.py`.

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
from app.modules.sensor_streams.schemas import AccSampleBatchRequest, SensorSampleBatchResponse
from app.modules.sensor_streams.services.sensor_stream_service import SensorStreamService
from app.security.rate_limiter import authenticated_caller_key, limiter

router = APIRouter()


@router.post(
    "/samples",
    response_model=SensorSampleBatchResponse,
    status_code=status.HTTP_201_CREATED,
    responses=SAMPLES_RESPONSES,
    summary="Store a batch of accelerometer samples",
    description=(
        "Bulk-inserts every sample in the batch into `hamsatech.acc_stream` for the "
        "authenticated athlete, resolved server-side from the access token — the request "
        "body never carries an athlete ID. The session must belong to that athlete. "
        "`accX`/`accY`/`accZ` are in milli-g; `recordedAt` must carry a UTC offset. "
        "Idempotent: `batchId` identifies the batch, so retrying with the same `batchId` never "
        "stores its samples twice and returns the original accepted count."
    ),
    tags=["ACC"],
    openapi_extra=request_body_openapi(AccSampleBatchRequest),
)
@limiter.limit(PER_CALLER_LIMIT, key_func=authenticated_caller_key)
@limiter.limit(PER_IP_LIMIT)
async def record_acc_samples(
    request: Request,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    payload: AccSampleBatchRequest = Depends(batch_body(AccSampleBatchRequest)),
    service: SensorStreamService = Depends(get_sensor_stream_service),
) -> SensorSampleBatchResponse:
    """Store `payload`'s accelerometer samples for the authenticated athlete's own session."""
    return await service.record_acc_samples(identity.phone_number, payload)
