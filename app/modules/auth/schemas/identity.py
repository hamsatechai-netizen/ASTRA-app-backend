"""
Internal identity representation — not a request/response DTO.

This is the shape passed from the security layer to route handlers once a
token has been validated (see `dependencies/current_athlete.py`), distinct
from `AuthResponse` (an HTTP response body). Kept schema-only: no lookup or
validation logic lives here.
"""

from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


class AuthenticatedIdentity(BaseSchema):
    """Decoded, trusted identity extracted from a validated access token."""

    # `hamsatech.users.id` — distinct from `hamsatech.athletes.athlete_id`
    # (a different table, a different text-typed ID). See `AuthResponse`.
    user_id: UUID = Field(..., description="Subject of the token — the authenticated user's ID.")
    phone_number: str = Field(..., description="The user's verified phone number.")
