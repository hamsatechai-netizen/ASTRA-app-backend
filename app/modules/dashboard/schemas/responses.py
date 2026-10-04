"""Response DTOs for the dashboard module."""

from pydantic import Field

from app.schemas.base import BaseSchema


class DashboardHomeResponse(BaseSchema):
    """
    Returned by `GET /api/mobile/athletes/{athlete_id}/home`.

    Field names match what the existing Flutter client's dashboard
    consumer (`DashboardRepositoryImpl.getDashboardData` /
    `_fetchMobileHomeData`, hamsatech_app
    `lib/features/dashboard/data/repositories/dashboard_repository_impl.dart:51-97`)
    already reads via its own null-coalescing fallback logic — not an
    invented shape.

    That same Flutter code also opportunistically reads `streak_days`/
    `streak` and `ai_insights`/`insights`/`recommendations` from this
    response, falling back to its existing local-only value when a key is
    absent. Both are deliberately NOT included here:

    - Streak requires a real day-counting algorithm (definition of a
      "day," timezone handling, reset logic) — that is a separate,
      not-yet-implemented feature, out of scope for this endpoint.
    - AI insights have no legitimate, non-fabricated backend source at
      this endpoint today. A separate, already-working fallback
      (`ApiService.getAiInsights`, a direct Supabase read of the existing
      `ai_insights` table) already covers this independently and is
      untouched by this change.

    Neither omission breaks the Flutter client: both reads are already
    null-safe and simply keep whatever locally-computed value they had.

    Readiness/Recovery/Stress/Steady are never read from this endpoint by
    the Flutter client at all (they are computed entirely client-side from
    onboarding baseline + local daily check-in) — there is no existing
    wire contract expecting them here, so none is included.
    """

    athlete_id: str = Field(..., description="The athlete's ID.")
    athlete_name: str | None = Field(None, description="Athlete's full name, if set.")
    sessions_this_week: int = Field(
        ...,
        description="Count of the athlete's completed sessions since the start of the current week (UTC).",
    )
    weekly_avg_score: float | None = Field(
        None,
        description=(
            "Average of shooting_session_log.avg_score across this week's completed sessions. "
            "Null if none of those sessions has a score recorded yet — never fabricated as 0."
        ),
    )
