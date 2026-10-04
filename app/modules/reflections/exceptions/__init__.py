"""
Reflections-module-specific exceptions.

Subclasses the project-wide `AppException` hierarchy (via the local
`ReflectionException` marker base) so the already-registered global
handler in `app.exceptions.handlers` catches these automatically — same
pattern as `app.modules.sessions.exceptions` / `app.modules.scores.exceptions`.
`ForbiddenException` is not redefined here: the project-wide one already
has exactly the needed semantics.
"""

from app.exceptions import AppException, ForbiddenException, NotFoundException


class ReflectionException(AppException):
    """Common base for every exception raised within the reflections module."""


class AthleteNotFoundException(NotFoundException):
    """No `hamsatech.athletes` row exists for the authenticated athlete's phone number."""

    error_code = "ATHLETE_NOT_FOUND"
    message = "No athlete profile was found for the authenticated account."


class SessionNotFoundException(NotFoundException):
    """No `hamsatech.sessions` row exists for the given `session_id`."""

    error_code = "SESSION_NOT_FOUND"
    message = "No session was found for the given session_id."


__all__ = [
    "ReflectionException",
    "AthleteNotFoundException",
    "SessionNotFoundException",
    "ForbiddenException",
]
