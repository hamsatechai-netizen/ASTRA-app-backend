"""
Daily check-in-module-specific exceptions.

Subclasses the project-wide `AppException` hierarchy (via the local
`CheckinException` marker base) so the already-registered global handler
in `app.exceptions.handlers` catches these automatically — same pattern
as `app.modules.series.exceptions` / `app.modules.streak.exceptions`.
`ForbiddenException` is not redefined here: the project-wide one already
has exactly the needed semantics.
"""

from app.exceptions import AppException, ForbiddenException, NotFoundException


class CheckinException(AppException):
    """Common base for every exception raised within the daily check-in module."""


class AthleteNotFoundException(NotFoundException):
    """No `hamsatech.athletes` row exists for the authenticated athlete's phone number."""

    error_code = "ATHLETE_NOT_FOUND"
    message = "No athlete profile was found for the authenticated account."


__all__ = [
    "CheckinException",
    "AthleteNotFoundException",
    "ForbiddenException",
]
