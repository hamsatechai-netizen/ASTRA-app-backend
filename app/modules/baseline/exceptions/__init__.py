"""
Baseline-module-specific exceptions.

Subclasses the project-wide `AppException` hierarchy (via the local
`BaselineException` marker base) so the already-registered global handler
in `app.exceptions.handlers` catches these automatically — same pattern
as `app.modules.checkin.exceptions` / `app.modules.streak.exceptions`.
`ForbiddenException` is not redefined here: the project-wide one already
has exactly the needed semantics.
"""

from app.exceptions import AppException, ForbiddenException, NotFoundException


class BaselineException(AppException):
    """Common base for every exception raised within the baseline module."""


class AthleteNotFoundException(NotFoundException):
    """No `hamsatech.athletes` row exists for the authenticated athlete's phone number."""

    error_code = "ATHLETE_NOT_FOUND"
    message = "No athlete profile was found for the authenticated account."


class BaselineNotFoundException(NotFoundException):
    """The athlete has no `hamsatech.athlete_physiology` row yet."""

    error_code = "BASELINE_NOT_FOUND"
    message = "No baseline has been captured for this athlete yet."


__all__ = [
    "BaselineException",
    "AthleteNotFoundException",
    "BaselineNotFoundException",
    "ForbiddenException",
]
