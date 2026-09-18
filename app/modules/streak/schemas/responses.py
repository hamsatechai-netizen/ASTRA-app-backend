"""Response DTOs for the streak module."""

from datetime import date

from pydantic import Field

from app.schemas.base import BaseSchema


class StreakResponse(BaseSchema):
    """
    Returned by `GET /api/mobile/athletes/{athlete_id}/streak`.

    Replaces the two independent, disagreeing local calculations that
    previously existed client-side (`DashboardRepositoryImpl._calculateStreak`
    and `ProfileScreen._computeStreak`) — this is now the single source of
    truth, derived live from `hamsatech.sessions` on every request, never
    persisted as a separate stored value.

    Day boundaries are computed in UTC (see
    `app.modules.streak.services.streak_service` module docstring) — the
    same documented approximation already used for the dashboard's
    `sessions_this_week`, since no athlete timezone is collected anywhere
    in this system today.
    """

    athlete_id: str = Field(..., description="The athlete's ID.")
    current_streak: int = Field(
        ...,
        description=(
            "Consecutive active days ending at today or yesterday (a session today is not "
            "required for the streak to still show correctly) — 0 if the most recent active day "
            "was more than 1 day ago, or if there are no completed sessions at all."
        ),
    )
    longest_streak: int = Field(
        ..., description="The longest run of consecutive active days found anywhere in the athlete's history."
    )
    last_active_date: date | None = Field(
        None, description="The most recent UTC calendar date with a completed session, if any."
    )
