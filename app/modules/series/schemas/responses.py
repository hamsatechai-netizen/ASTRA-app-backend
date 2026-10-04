"""Response DTOs for the series module."""

from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


class SeriesResponse(BaseSchema):
    """Returned by `POST /api/mobile/athletes/{athlete_id}/sessions/{session_id}/series`."""

    session_id: UUID = Field(..., description="The session this series belongs to.")
    series_number: int = Field(..., description="1-indexed series number within the session.")
    total_score: float | None = Field(None, description="Total score for this series.")
    shots_fired: int | None = Field(None, description="Number of shots fired in this series.")
