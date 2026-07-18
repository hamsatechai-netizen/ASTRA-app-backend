"""
v2 API router aggregator.

`main.py` mounts `api_router` once, under `settings.API_V2_PREFIX`. The
auth module's router lives here now (moved from v1 — no behavior,
schema, or business-logic change, only the mount point). Future feature
routers introduced as v2 follow the same pattern.
"""

from fastapi import APIRouter

from app.modules.auth.routers import auth_router
from app.modules.onboarding.routers import onboarding_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(onboarding_router, prefix="/onboarding", tags=["Onboarding"])
