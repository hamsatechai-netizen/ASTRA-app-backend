"""
Shared pytest fixtures.

Required settings (`SECRET_KEY`, `DATABASE_URL`, `SUPABASE_URL`,
`SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `TWILIO_ACCOUNT_SID`,
`TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`) are given safe test defaults
*before* `app.main` is imported, since `get_settings()` is evaluated at
module import time and would otherwise fail fast (by design) in a bare
test environment.
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production-0123456789")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/astra_test")
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "test-twilio-account-sid")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-twilio-auth-token")
os.environ.setdefault("TWILIO_FROM_NUMBER", "+15005550006")
# Pinned (not just left unset) so tests never fall through to whatever a
# developer's local .env happens to set these to — pydantic-settings reads
# .env for any variable os.environ doesn't already define.
os.environ.setdefault("DATABASE_SSL_ROOT_CERT_PATH", "")
os.environ.setdefault("DATABASE_SSL_INSECURE", "false")

import pytest
from app.main import app as fastapi_app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(fastapi_app) as test_client:
        yield test_client
