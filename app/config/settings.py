"""
Application settings.

All configuration is environment-driven (12-factor). Values are loaded from
process environment variables and, for local development, from a `.env`
file (see `.env.example` for the full list of supported keys).

No secret ever has a usable default here — required values (SECRET_KEY,
DATABASE_URL) will raise a validation error at startup if missing, so a
misconfigured deployment fails fast instead of running insecurely.

`get_settings()` is cached with `lru_cache` so the environment is parsed
exactly once per process and the resulting `Settings` instance can be
safely depended on (via FastAPI's `Depends`) throughout the app.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import AnyHttpUrl, Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    ALLOWED_HOSTS: list[str] = ["*"]
    CORS_ORIGINS: list[AnyHttpUrl] = []
    CORS_ALLOW_CREDENTIALS: bool = True

    # --- Database ------------------------------------------------------------
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT_SECONDS: int = 30
    DATABASE_ECHO: bool = False

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
