"""
Psychology-assessment-specific exceptions.

Subclasses the project-wide `AppException` hierarchy (via the local
`PsychologyAssessmentException` marker base) so the already-registered
global handler in `app.exceptions.handlers` catches these automatically —
same pattern as `app.modules.onboarding.exceptions` /
`app.modules.auth.exceptions`.
"""

from app.exceptions import AppException, ConflictException, NotFoundException, ValidationException


class PsychologyAssessmentException(AppException):
    """Common base for every exception raised within the psychology-assessment module."""


class AthleteNotFoundException(NotFoundException):
    """No `hamsatech.athletes` row exists for the authenticated athlete's phone number."""

    error_code = "ATHLETE_NOT_FOUND"
    message = "No athlete profile was found for the authenticated account."


class InvalidQuestionException(ValidationException):
    """The given `questionNumber` does not match any row in `hamsatech.psychology_questions`."""

    error_code = "INVALID_QUESTION"
    message = "The specified question does not exist."


class InvalidOptionException(ValidationException):
    """The given `optionCode` is not one of the given question's options."""

    error_code = "INVALID_OPTION"
    message = "The specified option is not valid for this question."


class AssessmentIncompleteException(ConflictException):
    """The athlete has not yet answered all 25 questions; the assessment cannot be completed."""

    error_code = "ASSESSMENT_INCOMPLETE"
    message = "The psychology assessment is not yet complete."


__all__ = [
    "PsychologyAssessmentException",
    "AthleteNotFoundException",
    "InvalidQuestionException",
    "InvalidOptionException",
    "AssessmentIncompleteException",
]
