"""
v1 API router aggregator.

`main.py` mounts `api_router` once, under `settings.API_V1_PREFIX`.
Feature routers are included here — the auth module's router is the
first; registration, onboarding, dashboard, and profile routers will
follow the same pattern.
"""

from fastapi import APIRouter

from app.modules.auth.routers import auth_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
