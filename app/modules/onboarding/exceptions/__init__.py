"""
Onboarding-specific exceptions.

Subclasses the project-wide `AppException` hierarchy (via the local
`OnboardingException` marker base) so the already-registered global
handler in `app.exceptions.handlers` catches these automatically.
"""

from app.exceptions import AppException, NotFoundException


class OnboardingException(AppException):
    """Common base for every exception raised within the onboarding module."""


class AthleteNotFoundException(NotFoundException):
    """No `hamsatech.athletes` row exists for the authenticated athlete's phone number."""

    error_code = "ATHLETE_NOT_FOUND"
    message = "No athlete profile was found for the authenticated account."


__all__ = ["OnboardingException", "AthleteNotFoundException"]
