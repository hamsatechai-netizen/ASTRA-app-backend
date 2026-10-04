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
    `total_shots`, `avg_score`, `best_series_score`, `notes`) — none of
    those have a column on the existing `hamsatech.sessions` table, so they
    are accepted (ignored, per Pydantic's default `extra="ignore"`) rather
    than rejected, without inventing new columns to store them. Only
    `end_time` is set. `total_shots`/`avg_score`/`best_series_score` are
    redundant with, not lost from, this call being a no-op on them: the
    client persists the real values separately via
    `POST .../sessions/{session_id}/score` (`hamsatech.shooting_session_log`).

    SESSION-2 (verified against source, not assumed): the client previously
    also sent `total_score` and `performance_rating` here. Neither was ever
    given a column — `total_score` has no destination on this table or on
    `shooting_session_log`, and the real `hamsatech.session_post_log
    .performance_rating` column carries a different, already-in-use meaning
    (see `SessionPostLog`'s docstring), so mapping a client-computed rating
    onto it would silently corrupt unrelated data rather than just being
    ignored. Removed client-side rather than backed by new columns.
    """
