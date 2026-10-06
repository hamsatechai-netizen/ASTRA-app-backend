"""
Sensor-stream-module-specific exceptions.

Subclasses the project-wide `AppException` hierarchy so the
already-registered global handler in `app.exceptions.handlers` catches
these automatically — same pattern as `app.modules.heart_rate.exceptions`
(whose athlete/session errors these mirror, with the same error codes, so a
client handles both modules' failures identically).
"""

from app.exceptions import AppException, ForbiddenException, NotFoundException, ValidationException


class SensorStreamException(AppException):
    """Common base for every exception raised within the sensor-stream module."""


class AthleteNotFoundException(NotFoundException):
    """No `hamsatech.athletes` row exists for the authenticated athlete's phone number."""

    error_code = "ATHLETE_NOT_FOUND"
    message = "No athlete profile was found for the authenticated account."


class SessionNotFoundException(NotFoundException):
    """No `hamsatech.sessions` row exists for the given `session_id`."""

    error_code = "SESSION_NOT_FOUND"
    message = "No session was found for the given session_id."


class PayloadTooLargeException(SensorStreamException):
    """The request body exceeds the per-request byte limit for a sample batch."""

    status_code = 413
    error_code = "PAYLOAD_TOO_LARGE"
    message = "The request body is too large."


__all__ = [
    "SensorStreamException",
    "AthleteNotFoundException",
    "SessionNotFoundException",
    "PayloadTooLargeException",
    "ForbiddenException",
    "ValidationException",
]
