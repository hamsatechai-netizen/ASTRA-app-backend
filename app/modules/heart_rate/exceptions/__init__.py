"""
Heart-rate-module-specific exceptions.

Subclasses the project-wide `AppException` hierarchy (via the local
`HeartRateException` marker base) so the already-registered global
handler in `app.exceptions.handlers` catches these automatically — same
pattern as `app.modules.onboarding.exceptions` /
`app.modules.psychology_assessment.exceptions`.
"""

from app.exceptions import AppException, ForbiddenException, NotFoundException


class HeartRateException(AppException):
    """Common base for every exception raised within the heart-rate module."""


class AthleteNotFoundException(NotFoundException):
    """No `hamsatech.athletes` row exists for the authenticated athlete's phone number."""

    error_code = "ATHLETE_NOT_FOUND"
    message = "No athlete profile was found for the authenticated account."


class SessionNotFoundException(NotFoundException):
    """No `hamsatech.sessions` row exists for the given `session_id`."""

    error_code = "SESSION_NOT_FOUND"
    message = "No session was found for the given session_id."


__all__ = [
    "HeartRateException",
    "AthleteNotFoundException",
    "SessionNotFoundException",
    "ForbiddenException",
]
