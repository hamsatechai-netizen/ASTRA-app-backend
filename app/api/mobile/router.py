"""
Mobile API router aggregator.

`main.py` mounts `api_router` once, under `settings.API_MOBILE_PREFIX`
("/api/mobile"). This is a separate, unversioned namespace from
`/api/v1`/`/api/v2` — it exists only because the Flutter client already
calls a small number of endpoints under this exact path shape
(`/api/mobile/athletes/{athlete_id}/...`). Only the sessions,
session-HR-read-back, score, reflection, and series endpoints are
implemented here; other `/api/mobile/athletes/...` paths the client may
call remain unimplemented and are out of scope.
"""

from fastapi import APIRouter

from app.modules.heart_rate.routers import session_heart_rate_router
from app.modules.reflections.routers import session_reflection_router
from app.modules.scores.routers import score_router
from app.modules.series.routers import session_series_router
from app.modules.sessions.routers import session_router

api_router = APIRouter()

api_router.include_router(session_router, tags=["Sessions"])
api_router.include_router(session_heart_rate_router, tags=["Heart Rate"])
api_router.include_router(score_router, tags=["Scores"])
api_router.include_router(session_reflection_router, tags=["Reflections"])
api_router.include_router(session_series_router, tags=["Series"])
