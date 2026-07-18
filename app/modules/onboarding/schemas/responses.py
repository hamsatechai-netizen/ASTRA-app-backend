"""Response DTOs for the onboarding flow."""

from datetime import date

from pydantic import Field

from app.schemas.base import BaseSchema


class OnboardingStatusResponse(BaseSchema):
    """
    Current onboarding state for the authenticated athlete.

    Returned by `GET /api/v2/onboarding` and after a successful
    `PUT /api/v2/onboarding/step-1`. Personal-detail fields are `None`
    until Step 1 has been completed.
    """

    athlete_id: str = Field(..., description="The athlete's identifier (hamsatech.athletes.athlete_id).")
    current_onboarding_step: int = Field(..., description="The next onboarding step the client should show.")
    is_onboarding_complete: bool = Field(
        ..., description="Whether the athlete has completed every onboarding step."
    )
    full_name: str | None = Field(None, description="Set once Step 1 is completed.")
    date_of_birth: date | None = Field(None, description="Set once Step 1 is completed.")
    gender: str | None = Field(None, description="Set once Step 1 is completed.")
    city: str | None = Field(None, description="Set once Step 1 is completed.")
