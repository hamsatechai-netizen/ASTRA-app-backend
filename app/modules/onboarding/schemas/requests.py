"""Request DTOs for the onboarding flow."""

from datetime import date

from pydantic import Field

from app.modules.onboarding.constants import Gender
from app.schemas.base import BaseSchema


class OnboardingStep1Request(BaseSchema):
    """Request body for `PUT /api/v2/onboarding/step-1` (Personal Details)."""

    full_name: str = Field(
        ...,
        alias="fullName",
        min_length=1,
        description="Athlete's full name.",
        examples=["Jane Doe"],
    )
    date_of_birth: date = Field(
        ...,
        alias="dateOfBirth",
        description="Athlete's date of birth.",
        examples=["2005-04-12"],
    )
    gender: Gender = Field(..., description="Athlete's gender.", examples=["Female"])
    city: str = Field(..., min_length=1, description="Athlete's city.", examples=["Mumbai"])
