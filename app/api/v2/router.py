"""
v2 API router aggregator.

`main.py` mounts `api_router` once, under `settings.API_V2_PREFIX`. The
auth module's router lives here now (moved from v1 — no behavior,
schema, or business-logic change, only the mount point). Future feature
routers introduced as v2 follow the same pattern.
"""

from fastapi import APIRouter

from app.modules.academies.routers import academy_router
from app.modules.auth.routers import auth_router
from app.modules.heart_rate.routers import heart_rate_router
from app.modules.onboarding.routers import onboarding_router
from app.modules.psychology_assessment.routers import psychology_assessment_router
from app.modules.sensor_streams.routers import acc_router, ecg_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(onboarding_router, prefix="/onboarding", tags=["Onboarding"])
api_router.include_router(academy_router, prefix="/academies", tags=["Academies"])
api_router.include_router(
    psychology_assessment_router, prefix="/psychology-assessment", tags=["Psychology Assessment"]
)
api_router.include_router(heart_rate_router, prefix="/heart-rate", tags=["Heart Rate"])
api_router.include_router(ecg_router, prefix="/ecg", tags=["ECG"])
api_router.include_router(acc_router, prefix="/acc", tags=["ACC"])
