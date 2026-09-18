"""Request DTOs for the daily check-in module."""

from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

# Exact set of labels `SleepOption.label` already produces
# (hamsatech_app `lib/features/checkin/domain/entities/daily_checkin_entity.dart`)
# — not invented, this is the existing Flutter client's own closed set.
SleepBand = Literal["<5h", "5-6h", "6-7h", "7-8h", "8h+"]

# Exact set of `EmotionTag.name` values the existing Flutter client sends.
EmotionTagName = Literal["anxious", "confident", "focused", "distracted", "motivated", "calm"]


class SaveCheckinRequest(BaseSchema):
    """
    Request body for `POST /api/v1/checkin/daily`.

    Matches exactly what the existing, active Flutter client already
    sends (`ApiService.saveDailyCheckin`, hamsatech_app
    `lib/core/services/api_service.dart:155-173`) — no field was added,
    renamed, or removed to fit this schema.

    `athlete_id` is included because the existing Flutter contract already
    sends it, but it is never trusted as the identity authority: the
    service resolves the real athlete from the access token and rejects
    any mismatch (`ForbiddenException`, 403) before this value is used for
    anything (see `CheckinService.save_checkin`).

    `checkin_date` is deliberately NOT a field here — the existing Flutter
    client never sends one, and none is accepted: the date this check-in
    represents is always derived server-side from the current UTC date
    (see `CheckinService`), so no client-supplied value can ever create a
    past- or future-dated record.
    """

    athlete_id: str = Field(
        ..., min_length=1, description="Client-asserted athlete ID — verified against the token, not trusted."
    )
    mood: int = Field(..., ge=1, le=5, description="Self-reported mood, 1-5.")
    energy_level: int = Field(..., ge=1, le=10, description="Self-reported energy level, 1-10.")
    sleep_band: SleepBand = Field(..., description="One of the existing Flutter sleep-band labels.")
    tags: list[EmotionTagName] | None = Field(
        None, description="Optional emotion tags, from the existing Flutter set."
    )
    notes: str | None = Field(None, description="Optional free-text note.")
