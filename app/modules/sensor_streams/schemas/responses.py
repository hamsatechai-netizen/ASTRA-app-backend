"""Response DTOs for the ECG/ACC batch-ingestion flow."""

from pydantic import Field

from app.schemas.base import BaseSchema


class SensorSampleBatchResponse(BaseSchema):
    """Returned by `POST /api/v2/ecg/samples` and `POST /api/v2/acc/samples` — same shape as for HR."""

    accepted: int = Field(
        ...,
        description=(
            "Number of samples stored for this batch. For a repeated `batchId` this is the count "
            "accepted the first time — nothing is inserted again."
        ),
    )
    duplicate: bool = Field(
        False,
        description="True when this `batchId` had already been accepted and no samples were inserted.",
    )
