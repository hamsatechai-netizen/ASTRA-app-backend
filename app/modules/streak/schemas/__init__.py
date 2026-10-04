"""Streak module schemas — re-exported here for a single, stable import path."""

from app.common.responses import ErrorResponse
from app.modules.streak.schemas.responses import StreakResponse

__all__ = [
    "StreakResponse",
    "ErrorResponse",
]
