"""
Token issuance service.

Wraps `app.modules.auth.security` (pure JWT encode/decode infrastructure)
with the *business* decisions of which subject gets which claims, and any
refresh-token/session persistence — those decisions are Phase 2.
"""

from uuid import UUID

from app.modules.auth.schemas.responses import AuthResponse


class TokenService:
    """Issues, refreshes, and revokes auth tokens (not yet implemented)."""

    async def issue_tokens(self, athlete_id: UUID, is_new_athlete: bool) -> AuthResponse:
        """Issue a new access/refresh token pair for `athlete_id`."""
        raise NotImplementedError("Token issuance is implemented in a later phase.")

    async def refresh_access_token(self, refresh_token: str) -> AuthResponse:
        """Exchange a valid, unexpired refresh token for a new access token."""
        raise NotImplementedError("Token refresh is implemented in a later phase.")

    async def revoke_token(self, token: str) -> None:
        """Revoke `token` (logout)."""
        raise NotImplementedError("Token revocation is implemented in a later phase.")
