"""
Streak-module-specific exceptions.

Subclasses the project-wide `AppException` hierarchy (via the local
`StreakException` marker base) so the already-registered global handler in
`app.exceptions.handlers` catches these automatically — same pattern as
`app.modules.dashboard.exceptions` / `app.modules.profile.exceptions`.
`ForbiddenException` is not redefined here: the project-wide one already
has exactly the needed semantics.
"""

from app.exceptions import AppException, ForbiddenException, NotFoundException


class StreakException(AppException):
    """Common base for every exception raised within the streak module."""


class AthleteNotFoundException(NotFoundException):
    """No `hamsatech.athletes` row exists for the authenticated athlete's phone number."""

    error_code = "ATHLETE_NOT_FOUND"
    message = "No athlete profile was found for the authenticated account."


__all__ = [
    "StreakException",
    "AthleteNotFoundException",
    "ForbiddenException",
]
