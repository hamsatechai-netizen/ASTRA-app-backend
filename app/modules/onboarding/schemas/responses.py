"""Response DTOs for the onboarding flow."""

from datetime import date
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


class OnboardingStatusResponse(BaseSchema):
    """
    Current onboarding state for the authenticated athlete.

    Returned by `GET /api/v2/onboarding` and after a successful
    `PUT /api/v2/onboarding/step-{1,2,3,4,5,6}`. Each step's fields are
    `None` until that step has been completed. `is_onboarding_complete`
    is `True` once Step 6's fields have all been saved (the onboarding
    step counter itself caps at 6 — see `OnboardingService._to_response`).
    """

    athlete_id: str = Field(..., description="The athlete's identifier (hamsatech.athletes.athlete_id).")
    current_onboarding_step: int = Field(..., description="The next onboarding step the client should show.")
    is_onboarding_complete: bool = Field(
        ..., description="Whether the athlete has completed every onboarding step."
    )

    # --- Step 1: Personal Details ---
    full_name: str | None = Field(None, description="Set once Step 1 is completed.")
    date_of_birth: date | None = Field(None, description="Set once Step 1 is completed.")
    gender: str | None = Field(None, description="Set once Step 1 is completed.")
    city: str | None = Field(None, description="Set once Step 1 is completed.")

    # --- Step 2: Athletic Background ---
    discipline: str | None = Field(None, description="Set once Step 2 is completed.")
    experience_level: str | None = Field(None, description="Set once Step 2 is completed.")
    years_shooting: int | None = Field(None, description="Set once Step 2 is completed.")
    academy_id: UUID | None = Field(None, description="Set once Step 2 is completed.")

    # --- Step 3: Track Your Performance ---
    average_practice_score: float | None = Field(None, description="Set once Step 3 is completed.")
    target_score: float | None = Field(None, description="Set once Step 3 is completed.")
    performance_blockers: list[str] | None = Field(None, description="Set once Step 3 is completed.")
    goal_30_day: str | None = Field(None, description="Set once Step 3 is completed.")
    goal_6_month: str | None = Field(None, description="Set once Step 3 is completed.")

    # --- Step 4: Academic Profile (hamsatech.athlete_details) ---
    school_class: str | None = Field(None, description="Set once Step 4 is completed.")
    school_name: str | None = Field(None, description="Set once Step 4 is completed.")
    academic_performance: str | None = Field(None, description="Set once Step 4 is completed.")

    # --- Step 5: Lifestyle & Wellness (hamsatech.athlete_details) ---
    diet_type: str | None = Field(None, description="Set once Step 5 is completed.")
    outside_food_frequency: str | None = Field(None, description="Set once Step 5 is completed.")
    sleep_time: str | None = Field(None, description="Set once Step 5 is completed.")
    wake_time: str | None = Field(None, description="Set once Step 5 is completed.")

    # --- Step 6: Mental & Social Profile (hamsatech.athlete_details) ---
    friend_circle: str | None = Field(None, description="Set once Step 6 is completed.")
    anger_pattern: str | None = Field(None, description="Set once Step 6 is completed.")
    sadness_pattern: str | None = Field(None, description="Set once Step 6 is completed.")
    reason_for_shooting: str | None = Field(None, description="Set once Step 6 is completed.")
    athlete_goal: str | None = Field(None, description="Set once Step 6 is completed.")
