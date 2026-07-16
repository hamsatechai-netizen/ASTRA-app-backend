"""
Tests for the database SSL context builder.

These specifically verify the safety guarantee behind `DATABASE_SSL_INSECURE`:
it must have zero effect unless explicitly opted into, and it must be
impossible for it to take effect when `ENVIRONMENT=production`, regardless
of how it's set. This is infrastructure/configuration behavior, not
business logic.
"""

import ssl

import pytest
from app.config.settings import Settings
from app.database.session import _build_ssl_context

BASE_ENV = {
    "SECRET_KEY": "test-secret-key-do-not-use-in-production-0123456789",
    "DATABASE_URL": "postgresql+asyncpg://postgres:pw@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres",
    "SUPABASE_URL": "https://ref.supabase.co",
    "SUPABASE_ANON_KEY": "anon",
    "SUPABASE_SERVICE_ROLE_KEY": "service",
    "TWILIO_ACCOUNT_SID": "AC_test",
    "TWILIO_AUTH_TOKEN": "test_token",
    "TWILIO_FROM_NUMBER": "+15005550006",
}


def _settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    for key, value in {**BASE_ENV, **overrides}.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_default_is_full_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    assert _build_ssl_context(settings) is True


def test_insecure_flag_is_a_noop_when_false(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, DATABASE_SSL_INSECURE="false")
    assert _build_ssl_context(settings) is True


def test_insecure_flag_skips_verification_in_local_env(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, ENVIRONMENT="local", DATABASE_SSL_INSECURE="true")
    context = _build_ssl_context(settings)
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE


def test_insecure_flag_is_refused_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, ENVIRONMENT="production", DATABASE_SSL_INSECURE="true")
    with pytest.raises(RuntimeError, match="production"):
        _build_ssl_context(settings)


def test_production_without_insecure_flag_still_gets_full_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, ENVIRONMENT="production")
    assert _build_ssl_context(settings) is True


def test_ca_path_takes_priority_over_insecure_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(
        monkeypatch,
        DATABASE_SSL_INSECURE="true",
        DATABASE_SSL_ROOT_CERT_PATH="certs/does-not-exist.crt",
    )
    # A configured (if broken) CA path is handled before the insecure flag is
    # ever consulted — should raise the missing-file error, not silently
    # fall through to the insecure context.
    with pytest.raises(RuntimeError, match="no file exists"):
        _build_ssl_context(settings)
