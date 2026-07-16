"""
Application exception hierarchy.

Services and repositories raise these instead of raw `HTTPException` so that
the domain/application layers stay framework-agnostic (they don't need to
know about HTTP status codes to signal an error) while still mapping
cleanly to a status code at the edge via `exceptions/handlers.py`.
"""

from typing import Any


class AppException(Exception):
    """Base class for all application-raised (expected) errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_SERVER_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details: Any | None = None) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)


class NotFoundException(AppException):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "The requested resource was not found."


class ValidationException(AppException):
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "Validation failed."


class UnauthorizedException(AppException):
    status_code = 401
    error_code = "UNAUTHORIZED"
    message = "Authentication is required."


class ForbiddenException(AppException):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "You do not have permission to perform this action."


class ConflictException(AppException):
    status_code = 409
    error_code = "CONFLICT"
    message = "The request could not be completed due to a conflict."


class RateLimitExceededException(AppException):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests. Please try again later."
