"""Request DTOs for the series module."""

from pydantic import Field

from app.schemas.base import BaseSchema


class SaveSeriesRequest(BaseSchema):
    """
    Request body for `POST .../sessions/{session_id}/series`.

    Matches exactly what `ScoreEntryBloc._syncSeries` already sends per
    completed series — this endpoint persists it, it does not recompute
    or derive anything from it.
    """

    series_number: int = Field(..., ge=1, description="1-indexed series number within the session.")
    total_score: float = Field(..., ge=0, description="Total score for this series.")
    shots_fired: int = Field(..., ge=0, description="Number of shots fired in this series.")
