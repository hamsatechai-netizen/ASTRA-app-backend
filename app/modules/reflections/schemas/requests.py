"""Request DTOs for the reflections module."""

from pydantic import Field

from app.schemas.base import BaseSchema


class SaveReflectionRequest(BaseSchema):
    """
    Request body for `POST .../sessions/{session_id}/reflection`.

    Mirrors what `ReflectScreen` already collects client-side — mood on
    the app's existing 1-5 `SessionMood.rating` scale, plus two free-text
    fields. All three are optional/nullable: an athlete may leave any of
    them blank, matching the existing screen's behavior.
    """

    mood: int | None = Field(None, ge=1, le=5, description="Self-reported mood, 1-5, or null.")
    what_worked: str | None = Field(None, description="Free text: what worked this session.")
    what_didnt: str | None = Field(None, description="Free text: what didn't work this session.")
