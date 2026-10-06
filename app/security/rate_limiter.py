"""
Rate limiting configuration.

Defines a single, shared `Limiter` (slowapi, backed by `limits`) keyed by
client IP. Registered on `app.state` and wired to the `RateLimitExceeded`
handler in `main.py`. Every route gets `RATE_LIMIT_DEFAULT` per client IP
(scoped per route) via `SlowAPIMiddleware`, except routes that declare
their own `@limiter.limit(...)` — currently only the ECG/ACC batch
ingestion routes (see `app.modules.sensor_streams.routers`), which use
`authenticated_caller_key` alongside a higher per-IP ceiling.
"""

import hashlib

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config.settings import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    enabled=settings.RATE_LIMIT_ENABLED,
)


def authenticated_caller_key(request: Request) -> str:
    """
    Rate-limit key for one authenticated caller rather than one IP address.

    Many athletes can share a single public IP (e.g. an academy's Wi-Fi), so
    a per-IP limit alone would throttle a whole squad as one client. Keyed
    on a SHA-256 digest of the Bearer token (the raw token is never stored
    as a key or logged); falls back to the client IP when no Bearer token
    is present. Only used on routes that already require authentication, by
    which point the token has been validated.
    """
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        return "bearer:" + hashlib.sha256(token.encode()).hexdigest()
    return get_remote_address(request)
