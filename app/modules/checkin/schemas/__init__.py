"""Daily check-in module schemas — re-exported here for a single, stable import path."""

from app.common.responses import ErrorResponse
from app.modules.checkin.schemas.requests import SaveCheckinRequest
from app.modules.checkin.schemas.responses import CheckinResponse

__all__ = [
    "SaveCheckinRequest",
    "CheckinResponse",
    "ErrorResponse",
]
