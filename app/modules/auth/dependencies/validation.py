"""
Request-level validation dependency placeholder.

For cross-field or cross-request checks that don't fit inside a single
Pydantic schema (e.g. confirming a verify-otp request corresponds to an
active send-otp challenge). Per-field format validation is already
handled declaratively by the request schemas themselves (see
`app.modules.auth.schemas.requests` and `app.modules.auth.validators`) —
this is for validation that needs more context than a single field.
"""

from fastapi import Request


async def validate_auth_request(request: Request) -> None:
    """Placeholder for request-level (cross-field/cross-request) validation."""
    raise NotImplementedError("Request-level validation is implemented in a later phase.")
