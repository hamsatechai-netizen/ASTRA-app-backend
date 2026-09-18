"""Baseline module schemas — re-exported here for a single, stable import path."""

from app.common.responses import ErrorResponse
from app.modules.baseline.schemas.requests import SaveBaselineRequest
from app.modules.baseline.schemas.responses import BaselineResponse

__all__ = [
    "SaveBaselineRequest",
    "BaselineResponse",
    "ErrorResponse",
]
