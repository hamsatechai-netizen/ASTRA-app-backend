"""Response DTOs for the baseline module."""

from datetime import date, datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class BaselineResponse(BaseSchema):
    """
    Returned by both `POST` and `GET /api/mobile/athletes/{athlete_id}/baseline`.

    Reflects exactly what was persisted in `hamsatech.athlete_physiology` —
    never fabricated. `session_id` is always `null` for a row created by
    this module (the resting-HR capture happens during onboarding, before
    any training session exists). No internal/security field (e.g. the
    synthetic `physiology_id` primary key) is included.
    """

    athlete_id: str = Field(..., description="The athlete's ID.")
    resting_heart_rate: int | None = Field(None, description="Captured resting heart rate, in BPM.")
    recorded_date: date | None = Field(None, description="The UTC calendar date this baseline was captured.")
    session_id: str | None = Field(
        None,
        description="The training session this row is associated with, if any (always null for a "
        "baseline captured during onboarding).",
    )
    created_at: datetime | None = Field(None, description="When this baseline row was created.")
