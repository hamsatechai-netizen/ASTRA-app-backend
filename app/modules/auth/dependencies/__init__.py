"""Auth module FastAPI dependencies — re-exported here for a single, stable import path."""

from app.modules.auth.dependencies.authorization import require_authorization
from app.modules.auth.dependencies.current_athlete import get_current_athlete, get_optional_current_athlete
from app.modules.auth.dependencies.services import get_auth_service, get_otp_repository, get_otp_service
from app.modules.auth.dependencies.validation import validate_auth_request

__all__ = [
    "get_current_athlete",
    "get_optional_current_athlete",
    "require_authorization",
    "validate_auth_request",
    "get_otp_repository",
    "get_otp_service",
    "get_auth_service",
]
