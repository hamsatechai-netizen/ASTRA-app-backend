"""
Current-athlete dependencies.

Both use the standard Bearer security scheme (so Swagger shows the
"Authorize" lock and the correct `Authorization: Bearer <token>` shape)
and resolve to `AuthenticatedIdentity` by decoding the access token via
`app.modules.auth.security.decode_token` and loading the user through
`UserRepositoryInterface.get_by_id`.
"""

from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.exceptions import UnauthorizedException
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.auth.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


async def _resolve_identity(
    credentials: HTTPAuthorizationCredentials, user_repository: UserRepositoryInterface
) -> AuthenticatedIdentity:
    claims = decode_token(credentials.credentials)
    if claims.get("type") != "access":
        raise UnauthorizedException("An access token is required.")

    try:
        user_id = UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise UnauthorizedException() from exc

    user = await user_repository.get_by_id(user_id)
    if user is None or user.phone_number is None:
        raise UnauthorizedException()

    return AuthenticatedIdentity(user_id=user.id, phone_number=user.phone_number)


async def get_current_athlete(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user_repository: UserRepositoryInterface = Depends(get_user_repository),
) -> AuthenticatedIdentity:
    """Resolve the caller's identity from a required Bearer token, or raise `UnauthorizedException`."""
    if credentials is None:
        raise UnauthorizedException()
    return await _resolve_identity(credentials, user_repository)


async def get_optional_current_athlete(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user_repository: UserRepositoryInterface = Depends(get_user_repository),
) -> AuthenticatedIdentity | None:
    """
    Resolve the caller's identity if a Bearer token is present, else `None`.

    For routes that behave differently for authenticated vs. anonymous
    callers without requiring authentication outright.
    """
    if credentials is None:
        return None
    return await _resolve_identity(credentials, user_repository)
