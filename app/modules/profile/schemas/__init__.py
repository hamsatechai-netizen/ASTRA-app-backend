"""Profile module schemas — re-exported here for a single, stable import path."""

from app.common.responses import ErrorResponse
from app.modules.profile.schemas.requests import UpdateProfileRequest
from app.modules.profile.schemas.responses import ProfileResponse

__all__ = [
    "UpdateProfileRequest",
    "ProfileResponse",
    "ErrorResponse",
]
