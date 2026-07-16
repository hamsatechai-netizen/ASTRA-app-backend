"""
Current-athlete dependencies.

Both use the standard Bearer security scheme (so Swagger shows the
"Authorize" lock and the correct `Authorization: Bearer <token>` shape)
and resolve to `AuthenticatedIdentity`. Actual token verification is
Phase 2 — see `app.modules.auth.security.decode_token` and the future
`AuthRepositoryInterface` lookup — so both raise `NotImplementedError`
for now rather than silently accept any token as valid.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.auth.schemas.identity import AuthenticatedIdentity

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_athlete(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedIdentity:
    """
    Resolve the caller's identity from a required Bearer token.

    Phase 2 will decode/verify the token via
    `app.modules.auth.security.decode_token` and load the athlete through
    `AuthRepositoryInterface`, raising `UnauthorizedException` if the
    token is missing or invalid.
    """
    raise NotImplementedError("Token verification is implemented in a later phase.")


async def get_optional_current_athlete(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedIdentity | None:
    """
    Resolve the caller's identity if a Bearer token is present, else `None`.

    For routes that behave differently for authenticated vs. anonymous
    callers without requiring authentication outright.
    """
    if credentials is None:
        return None
    raise NotImplementedError("Token verification is implemented in a later phase.")
