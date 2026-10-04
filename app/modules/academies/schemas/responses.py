"""Response DTOs for the academies listing."""

from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


class AcademyResponse(BaseSchema):
    """A single academy, as the Flutter onboarding Step 2 picker needs it."""

    academy_id: UUID = Field(
        ..., alias="academyId", description="Academy's unique identifier (hamsatech.academies.academy_id)."
    )
    academy_name: str = Field(..., alias="academyName", description="Academy's name.")
    location: str | None = Field(None, alias="location", description="Academy's location, if set.")
