"""
v1 API router aggregator.

`main.py` mounts `api_router` once, under `settings.API_V1_PREFIX`. Feature
routers are included here — none exist yet; this phase ships only the
aggregator so future endpoints (OTP, registration, onboarding, dashboard,
profile) have a single, obvious place to register.

Example of how a future feature router will be wired in:

    from app.api.v1.endpoints import auth
    api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
"""

from fastapi import APIRouter

api_router = APIRouter()
