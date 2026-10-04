"""Request DTOs for the onboarding flow."""

from datetime import date
from uuid import UUID

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


class OnboardingStep2Request(BaseSchema):
    """Request body for `PUT /api/v2/onboarding/step-2` (Athletic Background)."""

    discipline: str = Field(..., min_length=1, description="Shooting discipline.", examples=["10m Air Rifle"])
    experience_level: str = Field(
        ...,
        alias="experienceLevel",
        min_length=1,
        description="Experience level.",
        examples=["1 - 2 Years (Intermediate)"],
    )
    years_shooting: int = Field(..., alias="yearsShooting", ge=0, description="Years of shooting experience.")
    academy_id: UUID = Field(
        ..., alias="academyId", description="Athlete's academy (hamsatech.academies.academy_id)."
    )


class OnboardingStep3Request(BaseSchema):
    """Request body for `PUT /api/v2/onboarding/step-3` (Track Your Performance)."""

    average_practice_score: float = Field(
        ..., alias="averagePracticeScore", description="Average practice score."
    )
    target_score: float = Field(..., alias="targetScore", description="Target score goal.")
    performance_blockers: list[str] = Field(
        ..., alias="performanceBlockers", description="Self-reported performance blockers."
    )
    goal_30_day: str = Field(..., alias="goal30Day", min_length=1, description="30-day goal.")
    goal_6_month: str = Field(..., alias="goal6Month", min_length=1, description="6-month goal.")


class OnboardingStep4Request(BaseSchema):
    """Request body for `PUT /api/v2/onboarding/step-4` (Academic Profile)."""

    class_: str = Field(
        ..., alias="class", min_length=1, description="Current class/grade.", examples=["9th"]
    )
    school_name: str = Field(..., alias="schoolName", min_length=1, description="School name.")
    academic_performance: str = Field(
        ..., alias="academicPerformance", min_length=1, description="Self-reported academic performance."
    )


class OnboardingStep5Request(BaseSchema):
    """Request body for `PUT /api/v2/onboarding/step-5` (Lifestyle & Wellness)."""

    diet_type: str = Field(..., alias="dietType", min_length=1, description="Diet type.", examples=["Mix"])
    outside_food_frequency: str = Field(
        ..., alias="outsideFoodFrequency", min_length=1, description="How often outside food is eaten."
    )
    sleep_time: str = Field(..., alias="sleepTime", min_length=1, description="Usual sleep time.")
    wake_time: str = Field(..., alias="wakeTime", min_length=1, description="Usual wake time.")


class OnboardingStep6Request(BaseSchema):
    """Request body for `PUT /api/v2/onboarding/step-6` (Mental & Social Profile)."""

    friend_circle: str = Field(
        ..., alias="friendCircle", min_length=1, description="Friend circle description."
    )
    anger_pattern: str = Field(
        ..., alias="angerPattern", min_length=1, description="Anger pattern description."
    )
    sadness_pattern: str = Field(
        ..., alias="sadnessPattern", min_length=1, description="Sadness pattern description."
    )
    reason_for_shooting: str = Field(
        ..., alias="reasonForShooting", min_length=1, description="Reason for taking up shooting."
    )
    athlete_goal: str = Field(..., alias="athleteGoal", min_length=1, description="Athlete's overall goal.")
