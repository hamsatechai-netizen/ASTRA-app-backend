"""
v1 API router aggregator.

`main.py` mounts `api_router` once, under `settings.API_V1_PREFIX`. The
auth module's router moved to `app/api/v2/router.py` (see that module).
No v1 feature routers exist at present; this aggregator is kept mounted
(empty) so the versioned-namespace pattern is ready for any endpoint that
is deliberately introduced as v1 in the future.
"""

from fastapi import APIRouter

api_router = APIRouter()
