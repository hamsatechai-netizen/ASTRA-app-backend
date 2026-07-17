"""
Token issuance service.

Wraps `app.modules.auth.security` (pure JWT encode/decode infrastructure)
with the *business* decision of which subject gets which claims. Returns
only token material — `TokenPair` — not the full `AuthResponse`: which
user/onboarding-status fields go alongside the tokens is `AuthService`'s
job to assemble, not this service's concern.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.auth.constants import ACCESS_TOKEN_EXPIRE_MINUTES
from app.modules.auth.security import create_access_token, create_refresh_token


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


class TokenService:
    """Issues, refreshes, and revokes auth tokens."""

    async def issue_tokens(self, subject: UUID) -> TokenPair:
        """Issue a new access/refresh token pair for `subject`."""
        return TokenPair(
            access_token=create_access_token(subject),
            refresh_token=create_refresh_token(subject),
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """Exchange a valid, unexpired refresh token for a new access token."""
        raise NotImplementedError("Token refresh is implemented in a later phase.")

    async def revoke_token(self, token: str) -> None:
        """Revoke `token` (logout)."""
        raise NotImplementedError("Token revocation is implemented in a later phase.")
