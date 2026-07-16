"""
Rate limiting configuration.

Defines a single, shared `Limiter` (slowapi, backed by `limits`) keyed by
client IP. Registered on `app.state` and wired to the `RateLimitExceeded`
handler in `main.py`. No route declares a `@limiter.limit(...)` yet — this
is the infrastructure future endpoints (OTP send/verify, in particular,
which must be rate-limited) will decorate with.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config.settings import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    enabled=settings.RATE_LIMIT_ENABLED,
)
