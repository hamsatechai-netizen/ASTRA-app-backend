"""Request DTOs for the heart-rate ingestion flow."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema

_MIN_BPM = 30
_MAX_BPM = 250
_MIN_RR_MS = 200
_MAX_RR_MS = 3000
_MAX_BATCH_SIZE = 500


class HrSampleItem(BaseSchema):
    """One HR sample as streamed off the Polar device."""

    session_id: UUID = Field(
        ...,
        alias="sessionId",
        description="Client-generated ID grouping every sample from one Live Training recording.",
    )
    recorded_at: datetime = Field(
        ..., alias="recordedAt", description="When this sample was captured (device/client time)."
    )
    heart_rate: int = Field(
        ..., alias="heartRate", ge=_MIN_BPM, le=_MAX_BPM, description="Heart rate in bpm.", examples=[97]
    )
    rr_interval: int | None = Field(
        None,
        alias="rrInterval",
        ge=_MIN_RR_MS,
        le=_MAX_RR_MS,
        description="RR interval in milliseconds, if the device reported one.",
    )


class HrSampleBatchRequest(BaseSchema):
    """Request body for `POST /api/v2/heart-rate/samples` — a batch of samples from one upload."""

    samples: list[HrSampleItem] = Field(
        ..., min_length=1, max_length=_MAX_BATCH_SIZE, description="HR samples to store, in any order."
    )
