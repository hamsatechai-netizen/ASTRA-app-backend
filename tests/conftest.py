"""
Shared pytest fixtures.

Required settings (`SECRET_KEY`, `DATABASE_URL`) are given safe test
defaults *before* `app.main` is imported, since `get_settings()` is
evaluated at module import time and would otherwise fail fast (by design)
in a bare test environment.
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production-0123456789")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/astra_test")

import pytest
from app.main import app as fastapi_app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(fastapi_app) as test_client:
        yield test_client
