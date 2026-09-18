"""
Mobile API router aggregator.

`main.py` mounts `api_router` once, under `settings.API_MOBILE_PREFIX`
("/api/mobile"). This is a separate, unversioned namespace from
`/api/v1`/`/api/v2` — it exists only because the Flutter client already
calls a small number of endpoints under this exact path shape
(`/api/mobile/athletes/{athlete_id}/...`). Only the sessions,
session-HR-read-back, score, reflection, series, session-report, profile,
dashboard-home, streak, and baseline endpoints are implemented here;
other `/api/mobile/athletes/...` paths the client may call remain
unimplemented and are out of scope.
"""

from fastapi import APIRouter

from app.modules.baseline.routers import baseline_router
from app.modules.dashboard.routers import dashboard_router
from app.modules.heart_rate.routers import session_heart_rate_router
from app.modules.profile.routers import profile_router
from app.modules.reflections.routers import session_reflection_router
from app.modules.scores.routers import score_router
from app.modules.series.routers import session_series_router
from app.modules.session_report.routers import session_report_router
from app.modules.sessions.routers import session_router
from app.modules.streak.routers import streak_router

api_router = APIRouter()

api_router.include_router(session_router, tags=["Sessions"])
api_router.include_router(session_heart_rate_router, tags=["Heart Rate"])
api_router.include_router(score_router, tags=["Scores"])
api_router.include_router(session_reflection_router, tags=["Reflections"])
api_router.include_router(session_series_router, tags=["Series"])
api_router.include_router(session_report_router, tags=["Session Report"])
api_router.include_router(profile_router, tags=["Profile"])
api_router.include_router(dashboard_router, tags=["Dashboard"])
api_router.include_router(streak_router, tags=["Streak"])
api_router.include_router(baseline_router, tags=["Baseline"])
