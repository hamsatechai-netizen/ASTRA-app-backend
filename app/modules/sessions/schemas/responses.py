"""Response DTOs for the sessions module."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


class SessionHistoryItem(BaseSchema):
    """
    One entry in a `GET /api/mobile/athletes/{athlete_id}/sessions` page.

    Only completed sessions are listed (`end_time IS NOT NULL`) — the same
    semantic the pre-existing (unrouted) `SessionsListScreen` already
    applied client-side by filtering to `SessionStatus.completed`. An
    in-progress session (created, never completed) is not history yet, so
    `end_time`/`duration_seconds` are never null here.

    Two categories of field are deliberately absent, for different reasons:

    - Pre-session subjective data (the old local flow's energy/focus/
      stress/confidence log) has no legitimate backend source at all —
      that data is written only via a direct Supabase call to
      `session_pre_log`, a table this backend has no model for.
    - Post-session reflection text (`hamsatech.session_post_log.what_worked`
      etc.) genuinely IS available server-side (via the `reflections`
      module), but is left out of this summary list by design to keep a
      history page lean — the full reflection, HR, and score breakdown for
      any one session is already served in full by
      `GET .../sessions/{session_id}/report`.
    """

    session_id: UUID = Field(..., description="The session's ID.")
    session_type: str | None = Field(None, description="Type of training session, if set.")
    start_time: datetime = Field(..., description="When the session started (server time, UTC).")
    end_time: datetime = Field(..., description="When the session was completed (server time, UTC).")
    duration_seconds: int = Field(..., description="end_time - start_time, in whole seconds.")
    avg_score: float | None = Field(None, description="Session average score, if a score summary was saved.")
    best_series_score: float | None = Field(
        None, description="Best single series score, if a score summary was saved."
    )
    total_shots: int | None = Field(None, description="Total shots recorded, if a score summary was saved.")
    series_count: int = Field(..., description="Number of per-series score rows saved for this session.")


class SessionResponse(BaseSchema):
    """
    Returned by `POST /api/mobile/athletes/{athlete_id}/sessions`.

    Field names are plain snake_case (matching the underlying
    `hamsatech.sessions` columns) rather than camelCase-aliased: the
    Flutter client already parses this exact shape (`session_id`/`id`)
    via `SessionSetupBloc._extractSessionId`.
    """

    session_id: UUID = Field(..., description="The newly created session's authoritative ID.")
    athlete_id: str = Field(..., description="The owning athlete's ID.")
    session_type: str | None = Field(None, description="Type of training session, if provided.")
    start_time: datetime = Field(..., description="When the session was created (server time, UTC).")
    end_time: datetime | None = Field(None, description="When the session ended, if completed.")
