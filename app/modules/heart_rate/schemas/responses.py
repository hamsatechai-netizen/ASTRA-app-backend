"""Response DTOs for the heart-rate ingestion flow."""

from pydantic import Field

from app.schemas.base import BaseSchema


class HrSampleBatchResponse(BaseSchema):
    """Returned by `POST /api/v2/heart-rate/samples`."""

    accepted: int = Field(..., description="Number of HR samples inserted into `hr_stream`.")
