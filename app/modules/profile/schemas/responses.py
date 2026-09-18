"""Response DTOs for the profile module."""

from datetime import date

from pydantic import Field

from app.schemas.base import BaseSchema


class ProfileResponse(BaseSchema):
    """
    Returned by both `GET` and `PUT /api/mobile/athletes/{athlete_id}/profile`.

    Field names are plain snake_case, chosen to match what the existing
    Flutter client's code that *actually executes* on the Profile screen
    already reads from this response — not an invented shape. Traced
    directly: `ProfileScreen._syncProfileFromApi`
    (hamsatech_app `lib/features/profile/presentation/screens/profile_screen.dart:59-111`)
    calls the API directly (bypassing `AuthBloc`) and reads the response as
    a flat object, trying fallback key names per field — `athlete_name`,
    `sport_domain`, `experience_level`, `goal_30`, `goal_6_month`, and a
    top-level `age` are each a key that screen's own fallback list already
    checks. A separate, unused code path
    (`auth_repository_impl.dart::getAthleteProfile`, only reachable via the
    `AuthBloc` get-profile flow that `ProfileScreen` never dispatches) has a
    comment claiming a `{"profile": {...}}` envelope; this response is
    intentionally flat instead, to match the code that actually runs.

    Never includes password/OTP/JWT/service-role/internal-security fields —
    every value here is one already collected during onboarding and shown
    back to the athlete about themselves.
    """

    athlete_id: str = Field(..., description="The athlete's ID.")
    athlete_name: str | None = Field(None, description="Athlete's full name, if set.")
    date_of_birth: date | None = Field(None, description="Date of birth, if set.")
    age: int | None = Field(None, description="Computed from date_of_birth; null if date_of_birth is unset.")
    gender: str | None = Field(None, description="Gender, if set.")
    sport_domain: str | None = Field(None, description="Shooting discipline / specialization, if set.")
    experience_level: str | None = Field(None, description="Experience level, if set.")
    goal_30: str | None = Field(None, description="30-day goal, if set.")
    goal_6_month: str | None = Field(None, description="6-month goal, if set.")
