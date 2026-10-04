"""Scores module schemas — re-exported here for a single, stable import path."""

from app.common.responses import ErrorResponse
from app.modules.scores.schemas.requests import SaveScoreRequest
from app.modules.scores.schemas.responses import ScoreResponse

__all__ = [
    "SaveScoreRequest",
    "ScoreResponse",
    "ErrorResponse",
]
