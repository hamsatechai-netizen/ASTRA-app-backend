"""Auth module routers — re-exported here for a single, stable import path."""

from app.modules.auth.routers.auth_router import router as auth_router

__all__ = ["auth_router"]
