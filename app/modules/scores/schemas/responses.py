"""Response DTOs for the scores module."""

from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


class ScoreResponse(BaseSchema):
    """Returned by `POST /api/mobile/athletes/{athlete_id}/sessions/{session_id}/score`."""

    session_id: UUID = Field(..., description="The session this score belongs to.")
    athlete_id: str = Field(..., description="The owning athlete's ID.")
    total_shots: int | None = Field(None, description="Total shots fired across all series.")
    avg_score: float | None = Field(None, description="Average score per shot.")
    best_series_score: float | None = Field(None, description="Highest single-series total.")
