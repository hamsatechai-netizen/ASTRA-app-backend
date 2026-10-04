"""Request DTOs for the profile module."""

from pydantic import Field

from app.schemas.base import BaseSchema


class UpdateProfileRequest(BaseSchema):
    """
    Request body for `PUT /api/mobile/athletes/{athlete_id}/profile`.

    All fields are optional — this is a partial update. Field names/aliases
    match the existing Flutter client's actual wire payload exactly
    (`ApiService.updateMobileAthleteProfile`, hamsatech_app
    `lib/core/services/api_service.dart:1006-1031`), which only includes a
    key in the JSON body when the corresponding value is non-null/non-empty.

    That same client method also accepts `familySupport` and
    `pressureSources` parameters, but its own implementation deliberately
    never puts them in the request body ("have no server-side field under
    any name and are intentionally not sent" — its own code comment) — so
    there is nothing to model for those here.
    """

    full_name: str | None = Field(
        None, alias="fullName", min_length=1, description="Athlete's full name.", examples=["Jane Doe"]
    )
    age: int | None = Field(
        None,
        ge=0,
        le=120,
        description=(
            "Accepted for client compatibility but not persisted: `hamsatech.athletes` stores "
            "`date_of_birth` (owned by onboarding Step 1), not a raw age integer. Storing a second, "
            "independently-editable age would create two conflicting sources of truth for the same "
            "fact. Same precedent as `CreateSessionRequest` accepting-but-ignoring client fields "
            "with no backing column."
        ),
    )
    discipline: str | None = Field(
        None, min_length=1, description="Shooting discipline / specialization.", examples=["10m Air Rifle"]
    )
    experience_level: str | None = Field(
        None,
        alias="experienceLevel",
        min_length=1,
        description="Experience level.",
        examples=["1 - 2 Years (Intermediate)"],
    )
    goal_30_day: str | None = Field(None, alias="goal30Days", min_length=1, description="30-day goal.")
    goal_6_month: str | None = Field(None, alias="goal6Months", min_length=1, description="6-month goal.")
