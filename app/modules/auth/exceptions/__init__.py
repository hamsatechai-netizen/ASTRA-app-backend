"""
Auth-specific exceptions.

Every exception here subclasses the project-wide `AppException` (via the
local `AuthException` marker base), so each is automatically caught by the
*already-registered* global handler in `app.exceptions.handlers` —
Starlette resolves exception handlers by walking the raised exception's
MRO, so no new `add_exception_handler(...)` call is required for any of
these. `Unauthorized` and `Forbidden` are not redefined here: the
project-wide `UnauthorizedException` / `ForbiddenException` already have
exactly the needed semantics and are re-exported below instead of
duplicated.
"""

from app.exceptions import (
    AppException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)


class AuthException(AppException):
    """Common base for every exception raised within the auth module."""


class InvalidOTPException(AuthException):
    status_code = 400
    error_code = "INVALID_OTP"
    message = "The provided OTP is invalid."


class OTPExpiredException(AuthException):
    status_code = 400
    error_code = "OTP_EXPIRED"
    message = "The OTP has expired. Please request a new one."


class TooManyAttemptsException(AuthException):
    status_code = 429
    error_code = "TOO_MANY_ATTEMPTS"
    message = "Too many attempts. Please try again later."


class UserNotFoundException(NotFoundException):
    """The referenced athlete/account does not exist. Inherits status 404 from `NotFoundException`."""

    error_code = "USER_NOT_FOUND"
    message = "No account was found for the given phone number."


class InvalidTokenException(AuthException):
    status_code = 401
    error_code = "INVALID_TOKEN"
    message = "The provided token is invalid or malformed."


class TokenExpiredException(AuthException):
    """
    Raised specifically for an otherwise well-formed, correctly-signed
    token whose `exp` has passed — distinct from `InvalidTokenException`
    (bad signature / malformed / wrong type) so a client can tell "log in
    again, nothing is actually broken" apart from a real configuration or
    tampering problem. Access tokens are short-lived (60 minutes) with no
    client-side refresh flow, so this is the expected, routine case.
    """

    status_code = 401
    error_code = "TOKEN_EXPIRED"
    message = "Your session has expired. Please log in again."


class SMSDeliveryException(AuthException):
    """Raised when the SMS provider fails to deliver a message. Never exposes provider internals."""

    status_code = 500
    error_code = "SMS_DELIVERY_FAILED"
    message = "Failed to send the SMS. Please try again later."


class IdentityConflictException(ConflictException):
    """
    A newly created athlete's generated `athlete_id` doesn't match the
    authenticated user's existing, non-null `uid`.

    Raised by `UserService.resolve_onboarding_status` before the new
    `athlete_id` is ever assigned to `user.uid` — the existing, non-null
    value is never overwritten. Onboarding does not continue: the
    exception propagates out of the request, so `get_db` rolls back the
    whole transaction, including the just-created (but not yet committed)
    `hamsatech.athletes` row.
    """

    error_code = "IDENTITY_CONFLICT"
    message = (
        "This account's identity mapping is in an inconsistent state and could not be resolved "
        "automatically."
    )


class UidAlreadyAssignedException(ConflictException):
    """
    The `athlete_id` just generated for a brand-new athlete is already held
    as `uid` by a *different* `hamsatech.users` row.

    Raised by `UserService.resolve_onboarding_status` before `user.uid` is
    assigned, so the other account's mapping is never reassigned and this
    account's `uid` is never set to a value that would violate the
    `users_uid_key` UNIQUE constraint. Like `IdentityConflictException`,
    the exception propagates out of the request so `get_db` rolls back the
    whole transaction, including the just-created (not yet committed)
    `hamsatech.users` and `hamsatech.athletes` rows.
    """

    error_code = "UID_ALREADY_ASSIGNED"
    message = (
        "The generated athlete identifier is already linked to another account, so this "
        "account's identity mapping could not be established."
    )


class AmbiguousAthleteMatchException(ConflictException):
    """
    More than one `hamsatech.athletes` row shares the phone number this
    login resolved to (no unique constraint exists on `contact_number` —
    see the Blocker B investigation). A phone number, though OTP-verified,
    is corroborating evidence, never sufficient proof, when it doesn't
    resolve to exactly one profile — never guessed through.

    Raised by `UserService.resolve_onboarding_status` at the very start,
    before any athlete-creation or uid decision is made for this login:
    with the match ambiguous, there is no safe way to tell whether this is
    a new or a returning athlete, so nothing is created, linked, or
    reassigned. The exception propagates out of the request so `get_db`
    rolls back the whole transaction, including the phone-verified
    `hamsatech.users` row `get_or_create_user` may have just created or
    updated earlier in the same request. Resolving the duplicate
    `hamsatech.athletes` rows requires manual, out-of-band reconciliation
    — this phone number cannot log in until then.
    """

    error_code = "AMBIGUOUS_ATHLETE_MATCH"
    message = (
        "This phone number matches more than one athlete profile and could not be resolved "
        "automatically. Please contact support."
    )


__all__ = [
    "AuthException",
    "InvalidOTPException",
    "OTPExpiredException",
    "TooManyAttemptsException",
    "UserNotFoundException",
    "InvalidTokenException",
    "SMSDeliveryException",
    "IdentityConflictException",
    "UidAlreadyAssignedException",
    "AmbiguousAthleteMatchException",
    # Reused, not duplicated:
    "UnauthorizedException",
    "ForbiddenException",
]
