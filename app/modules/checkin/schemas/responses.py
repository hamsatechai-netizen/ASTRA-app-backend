"""Response DTOs for the daily check-in module."""

from datetime import date, datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class CheckinResponse(BaseSchema):
    """
    Returned by `POST /api/v1/checkin/daily`.

    Reflects exactly what was persisted — every field comes directly from
    the `hamsatech.daily_checkins` row that was just inserted or updated,
    never fabricated. `checkin_date` is always the server-computed UTC
    calendar date (see `CheckinService`), regardless of what device-local
    time the athlete actually submitted at. No internal/security field
    (e.g. the synthetic `id` primary key) is included.
    """

    athlete_id: str = Field(..., description="The athlete's ID.")
    checkin_date: date = Field(..., description="The UTC calendar date this check-in represents.")
    mood: int = Field(..., description="Self-reported mood, 1-5.")
    energy_level: int = Field(..., description="Self-reported energy level, 1-10.")
    sleep_band: str = Field(..., description="Selected sleep-band label.")
    tags: list[str] = Field(default_factory=list, description="Selected emotion tags, if any.")
    notes: str | None = Field(None, description="Optional free-text note, if provided.")
    created_at: datetime | None = Field(
        None, description="When this athlete's check-in row was first created (stable across updates)."
    )
    updated_at: datetime | None = Field(None, description="When this row was last updated.")
