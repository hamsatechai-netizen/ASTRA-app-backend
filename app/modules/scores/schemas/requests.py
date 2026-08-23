"""Request DTOs for the scores module."""

from pydantic import Field

from app.schemas.base import BaseSchema


class SaveScoreRequest(BaseSchema):
    """
    Request body for `POST .../sessions/{session_id}/score`.

    Carries only the session-level values `ScoreEntryBloc` already
    computes client-side (`total_shots`, `avg_score`, `best_series_score`)
    — this endpoint persists them, it does not recompute or derive
    anything from them.
    """

    total_shots: int = Field(..., ge=0, description="Total shots fired across all series.")
    avg_score: float = Field(..., ge=0, description="Average score per shot.")
    best_series_score: float = Field(..., ge=0, description="Highest single-series total.")
