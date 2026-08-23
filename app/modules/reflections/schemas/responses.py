"""Response DTOs for the reflections module."""

from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


class ReflectionResponse(BaseSchema):
    """Returned by `POST /api/mobile/athletes/{athlete_id}/sessions/{session_id}/reflection`."""

    session_id: UUID = Field(..., description="The session this reflection belongs to.")
    mood: int | None = Field(None, description="Self-reported mood, 1-5, or null.")
    what_worked: str | None = Field(None, description="Free text: what worked this session.")
    what_didnt: str | None = Field(None, description="Free text: what didn't work this session.")
