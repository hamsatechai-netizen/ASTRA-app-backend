"""Dashboard module schemas — re-exported here for a single, stable import path."""

from app.common.responses import ErrorResponse
from app.modules.dashboard.schemas.responses import DashboardHomeResponse

__all__ = [
    "DashboardHomeResponse",
    "ErrorResponse",
]
