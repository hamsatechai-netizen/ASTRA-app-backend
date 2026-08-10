"""Response DTOs for the sessions module."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


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
