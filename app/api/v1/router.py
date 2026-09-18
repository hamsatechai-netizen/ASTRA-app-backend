"""
v1 API router aggregator.

`main.py` mounts `api_router` once, under `settings.API_V1_PREFIX`. The
auth module's router moved to `app/api/v2/router.py` (see that module).
The daily check-in endpoint is the first real v1 route, kept here
because it's the existing, already-active Flutter path
(`POST /api/v1/checkin/daily`) — no architectural reason to move it.
"""

from fastapi import APIRouter

from app.modules.checkin.routers import checkin_router

api_router = APIRouter()

api_router.include_router(checkin_router, tags=["Daily Check-in"])
