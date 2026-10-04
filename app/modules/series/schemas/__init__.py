"""Series module schemas — re-exported here for a single, stable import path."""

from app.common.responses import ErrorResponse
from app.modules.series.schemas.requests import SaveSeriesRequest
from app.modules.series.schemas.responses import SeriesResponse

__all__ = [
    "SaveSeriesRequest",
    "SeriesResponse",
    "ErrorResponse",
]
