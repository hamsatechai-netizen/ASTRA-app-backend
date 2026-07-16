"""
Application entry point / composition root.

`create_application()` assembles the FastAPI app: middleware stack, CORS,
exception handlers, rate limiting, and the versioned API router. Nothing
here contains business logic — it only wires together the pieces defined
in `app.core`, `app.middleware`, `app.security`, and `app.exceptions`.

Run locally with:  uvicorn app.main:app --reload
Run in production via the Gunicorn/Uvicorn worker config in `scripts/`.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router as api_router_v1
from app.config.settings import get_settings
from app.core.events import lifespan
from app.core.logging import configure_logging
from app.exceptions.handlers import register_exception_handlers
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.security.rate_limiter import limiter

settings = get_settings()
configure_logging()


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # --- Rate limiting -----------------------------------------------------
    app.state.limiter = limiter
    # See the note in exceptions/handlers.py: slowapi's handler is precisely
    # typed to `RateLimitExceeded`, which mypy flags against the wider
    # `Exception`-typed stub for `add_exception_handler`.
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    # --- Middleware stack (outermost first) ---------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestContextMiddleware)

    # --- Centralized exception handling -------------------------------------
    register_exception_handlers(app)

    # --- Versioned API ------------------------------------------------------
    app.include_router(api_router_v1, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
