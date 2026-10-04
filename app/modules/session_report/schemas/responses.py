"""Response DTOs for the session-report read endpoint."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


class SessionSummarySection(BaseSchema):
    """Session lifecycle metadata — always present."""

    session_type: str | None = Field(None, description="Type of training session, if provided.")
    started_at: datetime = Field(..., description="When the session was created (server time, UTC).")
    completed_at: datetime | None = Field(None, description="When the session ended, if completed.")
    duration_seconds: int | None = Field(
        None, description="Elapsed time between start and end, in seconds. Null until the session ends."
    )


class HeartRateSummarySection(BaseSchema):
    """
    Heart-rate statistics for the session, computed in SQL over every
    stored `hr_stream` sample. Always present — `sample_count` is 0 and
    every other field is null when the session has no HR data, matching
    the existing `SessionHrResponse` convention of never fabricating a value.
    """

    sample_count: int = Field(..., description="Total number of stored HR samples for this session.")
    average_heart_rate: int | None = Field(
        None, description="Average heart rate in bpm, or null if no samples."
    )
    minimum_heart_rate: int | None = Field(
        None, description="Minimum heart rate in bpm, or null if no samples."
    )
    maximum_heart_rate: int | None = Field(
        None, description="Maximum heart rate in bpm, or null if no samples."
    )
    first_heart_rate: int | None = Field(
        None, description="Earliest recorded heart rate in bpm, or null if no samples."
    )
    last_heart_rate: int | None = Field(
        None, description="Most recently recorded heart rate in bpm, or null if no samples."
    )


class ScoreSummarySection(BaseSchema):
    """
    Score data for the session, drawn from two independently-saved
    sources: the client-computed session summary (`total_shots`,
    `avg_score`, `best_series_score`, saved via the scores module) and
    statistics computed here over the session's saved series
    (`total_score`/`average_score`/`minimum_score`/`maximum_score`, each
    an aggregate of `session_series.total_score`). Either source may be
    absent independently — their fields are null, not fabricated, when
    that source has no data for this session.
    """

    total_shots: int | None = Field(None, description="Total shots fired, from the saved score summary.")
    avg_score: float | None = Field(None, description="Average score per shot, from the saved score summary.")
    best_series_score: float | None = Field(
        None, description="Highest single-series total, from the saved score summary."
    )
    total_score: float | None = Field(None, description="Sum of every saved series' total_score.")
    average_score: float | None = Field(None, description="Average of every saved series' total_score.")
    minimum_score: float | None = Field(None, description="Lowest saved series total_score.")
    maximum_score: float | None = Field(None, description="Highest saved series total_score.")


class SeriesEntryResponse(BaseSchema):
    """One saved series within the session."""

    series_number: int = Field(..., description="1-indexed series number within the session.")
    total_score: float | None = Field(None, description="Total score for this series.")
    shots_fired: int | None = Field(None, description="Number of shots fired in this series.")


class ReflectionSummarySection(BaseSchema):
    """The session's saved reflection, if any."""

    mood: int | None = Field(None, description="Self-reported mood rating.")
    what_worked: str | None = Field(None, description="What the athlete felt worked well.")
    what_didnt: str | None = Field(None, description="What the athlete felt didn't work.")


class SessionReportResponse(BaseSchema):
    """
    Returned by `GET /api/mobile/athletes/{athlete_id}/sessions/{session_id}/report`.

    Aggregates every table already persisted for one session. Contains
    only raw data and deterministic aggregates directly computed from
    stored rows — no Readiness/Recovery/Stress/Steady or any other derived
    metric, since no such algorithm has been defined or persisted yet.
    `scores` and `reflection` are null when that category has no data for
    this session; `series` is `[]` when none were saved. `heart_rate`
    is always present (see `HeartRateSummarySection`).
    """

    session_id: UUID = Field(..., description="The session this report covers.")
    athlete_id: str = Field(..., description="The owning athlete's ID.")
    session_status: str = Field(
        ..., description='"completed" if the session has an end_time, otherwise "in_progress".'
    )
    session_summary: SessionSummarySection
    heart_rate: HeartRateSummarySection
    scores: ScoreSummarySection | None = Field(
        None, description="Null when neither a score summary nor any series were saved for this session."
    )
    series: list[SeriesEntryResponse] = Field(
        default_factory=list, description="Every saved series for this session, ordered by series_number."
    )
    reflection: ReflectionSummarySection | None = Field(
        None, description="Null when no reflection was saved for this session."
    )
