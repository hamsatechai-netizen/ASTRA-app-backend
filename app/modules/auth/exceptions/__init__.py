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

from app.exceptions import AppException, ForbiddenException, NotFoundException, UnauthorizedException


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
    message = "The provided token is invalid, expired, or malformed."


class SMSDeliveryException(AuthException):
    """Raised when the SMS provider fails to deliver a message. Never exposes provider internals."""

    status_code = 500
    error_code = "SMS_DELIVERY_FAILED"
    message = "Failed to send the SMS. Please try again later."


__all__ = [
    "AuthException",
    "InvalidOTPException",
    "OTPExpiredException",
    "TooManyAttemptsException",
    "UserNotFoundException",
    "InvalidTokenException",
    "SMSDeliveryException",
    # Reused, not duplicated:
    "UnauthorizedException",
    "ForbiddenException",
]
