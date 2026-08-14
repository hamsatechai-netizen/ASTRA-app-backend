"""Request DTOs for the sessions module."""

from pydantic import Field

from app.schemas.base import BaseSchema


class CreateSessionRequest(BaseSchema):
    """
    Request body for `POST /api/mobile/athletes/{athlete_id}/sessions`.

    The Flutter client also sends `range_type`, `planned_shots`, and
    `discipline` today — none of those have a column on the existing
    `hamsatech.sessions` table, so they are accepted (ignored, per
    Pydantic's default `extra="ignore"`) rather than rejected, without
    inventing new columns to store them.
    """

    session_type: str | None = Field(
        None, description='Type of training session (e.g. "scoring", "grouping", "dry_fire").'
    )


class CompleteSessionRequest(BaseSchema):
    """
    Request body for `POST .../sessions/{session_id}/complete`.

    The Flutter client sends score-summary fields (`duration_minutes`,
    `total_shots`, `total_score`, `avg_score`, `best_series_score`,
    `performance_rating`, `notes`) — none of those have a column on the
    existing `hamsatech.sessions` table, so they are accepted (ignored, per
    Pydantic's default `extra="ignore"`) rather than rejected, without
    inventing new columns to store them. Only `end_time` is set.
    """
