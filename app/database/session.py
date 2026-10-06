"""
Async SQLAlchemy engine and session factory.

A single module-level engine is created per process (SQLAlchemy engines are
thread/task-safe and pool connections internally — they should never be
recreated per-request). `AsyncSessionFactory` is what `dependencies/database.py`
uses to hand each request its own `AsyncSession`.

The target database is Supabase PostgreSQL, reached over the network via
`DATABASE_URL` — there is no local database in this project. Two Supabase-
specific connection concerns are handled here rather than in the URL itself:
mandatory TLS (verified against Supabase's own CA via
`DATABASE_SSL_ROOT_CERT_PATH` — see `_build_ssl_context`; this is required
for every Supabase Postgres endpoint, direct connection and Supavisor
pooler alike, since both are issued from Supabase's own private CA — a
`DATABASE_SSL_INSECURE` escape hatch exists for local development before
that CA file is configured, disabled by default and refused outright in
production), and (optionally) asyncpg prepared-statement caching, which
must be disabled when connecting through Supabase's Supavisor pooler in
transaction mode.
"""

import ssl
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import Settings, get_settings

settings = get_settings()


def _build_ssl_context(settings: Settings) -> ssl.SSLContext | bool:
    """
    Build the `ssl` value passed to asyncpg's `connect()`.

    Plain `ssl=True` makes asyncpg call `ssl.create_default_context()`,
    which verifies against the *public* trust store (system or certifi).
    That is not sufficient for any Supabase Postgres endpoint: confirmed
    by directly inspecting the certificates both the direct-connection
    host and the Session Pooler (`*.pooler.supabase.com`) present, both
    are issued from Supabase's own private CA ("Supabase Intermediate
    2021 CA"), which no public trust store recognizes. Verification fails
    with "self-signed certificate in certificate chain" against *either*
    endpoint, transaction or session mode, regardless of which public
    trust store is used. This is not a missing/outdated-certificate
    problem; it's the wrong trust anchor.

    Two ways to actually connect, in order of preference:

    1. `DATABASE_SSL_ROOT_CERT_PATH` set to Supabase's actual CA file
       (downloaded from the dashboard) — full chain and hostname
       verification, just pointed at the right issuer, never disabled.
       Works in every environment, including production. If it's set but
       the file isn't actually there, we raise a clear, actionable error
       here rather than letting a bare `FileNotFoundError` surface from
       deep inside the `ssl` module.
    2. `DATABASE_SSL_INSECURE=true` — a **local-development-only**
       stopgap for when you don't have the CA file yet. Still encrypts
       the connection (TLS is negotiated either way); only skips
       certificate chain/hostname verification, so a network
       machine-in-the-middle would go undetected. Refuses to start if
       `ENVIRONMENT=production`, regardless of this flag, so it cannot
       silently weaken a production deployment. Must be removed before
       any real deployment — see `.env.example` and the README.
    """
    ca_path = (settings.DATABASE_SSL_ROOT_CERT_PATH or "").strip()
    if ca_path:
        if not Path(ca_path).is_file():
            raise RuntimeError(
                f"DATABASE_SSL_ROOT_CERT_PATH is set to {ca_path!r}, but no file exists "
                "there. Download the CA certificate from the Supabase dashboard "
                "(Project Settings -> Database -> SSL Configuration) and place it at "
                "that path — it is required for every Supabase Postgres endpoint, "
                "direct connection and Supavisor pooler alike."
            )
        return ssl.create_default_context(cafile=ca_path)

    if settings.DATABASE_SSL_INSECURE:
        if settings.is_production:
            raise RuntimeError(
                "DATABASE_SSL_INSECURE is set but ENVIRONMENT=production — refusing to "
                "start with database certificate verification disabled in production. "
                "Unset DATABASE_SSL_INSECURE and configure DATABASE_SSL_ROOT_CERT_PATH "
                "with Supabase's real CA certificate instead."
            )
        logger.warning(
            "DATABASE_SSL_INSECURE=true: the database connection is encrypted but its "
            "certificate is NOT being verified. Local development only — configure "
            "DATABASE_SSL_ROOT_CERT_PATH and remove this flag before deploying."
        )
        insecure_context = ssl.create_default_context()
        insecure_context.check_hostname = False
        insecure_context.verify_mode = ssl.CERT_NONE
        return insecure_context

    return True


def build_connect_args(settings: Settings) -> dict[str, Any]:
    """
    asyncpg connect() kwargs for Supabase.

    Shared with `migrations/env.py` and `scripts/wait_for_db.py` so every
    connection to Supabase — app, Alembic, or the startup readiness probe —
    negotiates TLS and (optionally) disables prepared-statement caching the
    same way.
    """
    connect_args: dict[str, Any] = {}
    if settings.DATABASE_SSL_REQUIRED:
        connect_args["ssl"] = _build_ssl_context(settings)
    if settings.DATABASE_USE_PGBOUNCER:
        connect_args["statement_cache_size"] = 0
    return connect_args


engine: AsyncEngine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT_SECONDS,
    pool_pre_ping=True,
    # Keep bound parameter values (athlete IDs, raw ECG/ACC samples, ...) out of
    # SQLAlchemy exception messages and echo logs — the unhandled-exception
    # handler logs those messages verbatim.
    hide_parameters=True,
    connect_args=build_connect_args(settings),
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
