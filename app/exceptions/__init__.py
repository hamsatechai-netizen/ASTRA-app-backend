"""
Exception architecture.

`base.py` defines the `AppException` hierarchy that services/repositories
raise instead of leaking framework- or driver-specific errors. `handlers.py`
registers the FastAPI exception handlers that translate those (and any
unhandled) exceptions into the standard `ErrorResponse` envelope.
"""

from app.exceptions.base import (
    AppException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    RateLimitExceededException,
    UnauthorizedException,
    ValidationException,
)
from app.exceptions.handlers import register_exception_handlers

__all__ = [
    "AppException",
    "ConflictException",
    "ForbiddenException",
    "NotFoundException",
    "RateLimitExceededException",
    "UnauthorizedException",
    "ValidationException",
    "register_exception_handlers",
]
