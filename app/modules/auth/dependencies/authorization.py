"""
Authorization helper.

A dependency *factory*: call it with the roles a route requires and get
back a FastAPI dependency. Kept generic rather than tied to a concrete
role enum, since no athlete/role model exists yet.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity


def require_authorization(*allowed_roles: str) -> Callable[..., Coroutine[Any, Any, AuthenticatedIdentity]]:
    """
    Build a dependency that requires the current athlete to hold one of
    `allowed_roles`.

    Not implemented: role/permission data doesn't exist yet, so the
    returned dependency always raises `NotImplementedError`. Once a role
    model exists, this will raise `ForbiddenException` on a mismatch.
    """

    async def _dependency(
        identity: AuthenticatedIdentity = Depends(get_current_athlete),
    ) -> AuthenticatedIdentity:
        raise NotImplementedError("Role/permission checks are implemented in a later phase.")

    return _dependency
