"""Response DTOs for the heart-rate ingestion and read-back flows."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


class HrSampleBatchResponse(BaseSchema):
    """Returned by `POST /api/v2/heart-rate/samples`."""

    accepted: int = Field(..., description="Number of HR samples inserted into `hr_stream`.")


class HrPointResponse(BaseSchema):
    """One (possibly downsampled) HR point in a session's chart series."""

    recorded_at: datetime = Field(..., description="When this HR sample was captured.")
    heart_rate: int = Field(..., description="Heart rate in bpm.")


class SessionHrResponse(BaseSchema):
    """
    Returned by `GET /api/mobile/athletes/{athlete_id}/sessions/{session_id}/heart-rate`.

    `avg_hr`/`min_hr`/`max_hr` are computed over every stored sample for the
    session; `points` is a chronologically-ordered, deterministically
    downsampled series (see `HeartRateService._MAX_CHART_POINTS`) for
    charting — not the raw sample set. All three aggregate fields and
    `points` are null/empty (never fabricated) when `sample_count` is 0.
    """

    session_id: UUID = Field(..., description="The session these HR stats belong to.")
    sample_count: int = Field(..., description="Total number of stored HR samples for this session.")
    avg_hr: int | None = Field(None, description="Average heart rate in bpm, or null if no samples.")
    min_hr: int | None = Field(None, description="Minimum heart rate in bpm, or null if no samples.")
    max_hr: int | None = Field(None, description="Maximum heart rate in bpm, or null if no samples.")
    points: list[HrPointResponse] = Field(
        default_factory=list, description="Downsampled, chronologically ordered HR points for charting."
    )
