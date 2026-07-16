"""
Application settings.

All configuration is environment-driven (12-factor). Values are loaded from
process environment variables and, for local development, from a `.env`
file (see `.env.example` for the full list of supported keys).

No secret ever has a usable default here — required values (SECRET_KEY,
DATABASE_URL, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY,
TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER) will raise a
validation error at startup if missing, so a misconfigured deployment
fails fast instead of running insecurely.

`get_settings()` is cached with `lru_cache` so the environment is parsed
exactly once per process and the resulting `Settings` instance can be
safely depended on (via FastAPI's `Depends`) throughout the app.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import AnyHttpUrl, Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Application -----------------------------------------------------
    APP_NAME: str = "ASTRA Backend"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "ASTRA backend service."
    ENVIRONMENT: Environment = Environment.LOCAL
    DEBUG: bool = False

    # --- API ---------------------------------------------------------------
    API_V1_PREFIX: str = "/api/v1"

    # --- Security ------------------------------------------------------------
    SECRET_KEY: str = Field(
        ..., min_length=32, description="Used for cryptographic signing. Never commit this."
    )
    # `NoDecode` tells pydantic-settings not to attempt its own JSON parse of
    # the raw .env string for these list-typed fields — without it, a plain
    # value like `ALLOWED_HOSTS=*` or a comma-separated `CORS_ORIGINS` fails
    # with a JSONDecodeError before our `_split_csv` validator below ever
    # runs. `NoDecode` passes the raw string straight through to it instead.
    ALLOWED_HOSTS: Annotated[list[str], NoDecode] = ["*"]
    CORS_ORIGINS: Annotated[list[AnyHttpUrl], NoDecode] = []
    CORS_ALLOW_CREDENTIALS: bool = True

    # --- Supabase project API ---------------------------------------------------
    # From the Supabase dashboard: Settings -> API. These are the credentials
    # for Supabase's own services (Auth, Storage, PostgREST, ...) accessed via
    # the official `supabase` client SDK — separate from DATABASE_URL below,
    # which is the raw Postgres connection SQLAlchemy/Alembic use directly.
    # SUPABASE_SERVICE_ROLE_KEY bypasses Row Level Security: server-side only,
    # never expose it to a client or log it.
    SUPABASE_URL: AnyHttpUrl
    SUPABASE_ANON_KEY: SecretStr
    SUPABASE_SERVICE_ROLE_KEY: SecretStr

    # --- Database (Supabase PostgreSQL) ---------------------------------------
    # DATABASE_URL is the Postgres connection string from the Supabase project
    # dashboard (Settings -> Database), using the asyncpg scheme, e.g.:
    #   postgresql+asyncpg://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
    # or, via the Supavisor connection pooler (see DATABASE_USE_PGBOUNCER below):
    #   postgresql+asyncpg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT_SECONDS: int = 30
    DATABASE_ECHO: bool = False
    # Supabase requires TLS on every connection; asyncpg needs this negotiated
    # explicitly rather than via a `sslmode=` query param (which it doesn't
    # understand — that's a libpq/psycopg convention).
    DATABASE_SSL_REQUIRED: bool = True
    # Set to true only when DATABASE_URL points at Supabase's Supavisor pooler
    # in *transaction* mode (port 6543). That mode doesn't support asyncpg's
    # server-side prepared-statement cache, so it must be disabled or every
    # query fails with "prepared statement ... does not exist". Direct
    # connections (port 5432) and *session*-mode pooler connections don't need
    # this.
    DATABASE_USE_PGBOUNCER: bool = False
    # Optional path to a CA bundle file used to verify DATABASE_URL's server
    # certificate. Every Supabase Postgres endpoint — direct connection
    # (db.<ref>.supabase.co) *and* the Supavisor pooler (*.pooler.supabase.com),
    # confirmed by inspecting both certificates directly — is issued from
    # Supabase's own private CA ("Supabase Intermediate 2021 CA"), which isn't
    # in any public trust store (system or certifi). Full verification
    # requires this: download the CA file from the Supabase dashboard
    # (Project Settings -> Database -> SSL Configuration).
    DATABASE_SSL_ROOT_CERT_PATH: str | None = None
    # DEV-ONLY escape hatch for local development when the CA file above
    # isn't configured yet. Encrypts the connection but skips certificate
    # chain/hostname verification — never honored when ENVIRONMENT=production
    # (app/database/session.py refuses to start rather than silently
    # downgrading security there). Must be false/unset before any deployment;
    # see README for the full checklist.
    DATABASE_SSL_INSECURE: bool = False

    # --- SMS provider (Twilio) — used by the auth module to deliver OTPs ------------
    TWILIO_ACCOUNT_SID: str = Field(..., description="Twilio Account SID.")
    TWILIO_AUTH_TOKEN: SecretStr = Field(
        ..., description="Twilio Auth Token — secret, authenticates all Twilio API requests."
    )
    TWILIO_FROM_NUMBER: str = Field(
        ..., description="E.164-formatted Twilio phone number that OTP SMS messages are sent from."
    )

    # --- Logging ------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # --- Rate limiting --------------------------------------------------------
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "60/minute"

    @field_validator("ALLOWED_HOSTS", "CORS_ORIGINS", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT is Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance."""
    return Settings()
