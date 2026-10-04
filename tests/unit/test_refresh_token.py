"""
Tests for token refresh — `TokenService.refresh_access_token` directly, and
the full `POST /api/v2/auth/refresh` router path.

`TokenService` has no repository dependency (see `get_token_service` in
`app.modules.auth.dependencies.services`), so the router-level tests here
use the plain `client` fixture with no `dependency_overrides` — unlike
`test_verify_otp.py`, this endpoint never touches the database.
"""

import uuid

import pytest
from app.modules.auth.constants import ACCESS_TOKEN_EXPIRE_MINUTES
from app.modules.auth.exceptions import InvalidTokenException, TokenExpiredException
from app.modules.auth.security.jwt import create_access_token, create_refresh_token, decode_token
from app.modules.auth.services.token_service import TokenService
from fastapi.testclient import TestClient

ENDPOINT = "/api/v2/auth/refresh"

# --- Service-level: TokenService.refresh_access_token ------------------------


async def test_refresh_access_token_issues_a_new_pair_for_the_same_subject() -> None:
    subject = uuid.uuid4()
    refresh_token = create_refresh_token(subject)
    service = TokenService()

    tokens = await service.refresh_access_token(refresh_token)

    access_claims = decode_token(tokens.access_token)
    refresh_claims = decode_token(tokens.refresh_token)
    assert access_claims["sub"] == str(subject)
    assert access_claims["type"] == "access"
    assert refresh_claims["sub"] == str(subject)
    assert refresh_claims["type"] == "refresh"
    assert tokens.expires_in == ACCESS_TOKEN_EXPIRE_MINUTES * 60


async def test_refresh_access_token_rejects_an_access_token_presented_as_refresh() -> None:
    access_token = create_access_token(uuid.uuid4())
    service = TokenService()

    with pytest.raises(InvalidTokenException):
        await service.refresh_access_token(access_token)


async def test_refresh_access_token_rejects_an_expired_refresh_token() -> None:
    expired_refresh_token = create_refresh_token(uuid.uuid4(), expires_days=-31)
    service = TokenService()

    with pytest.raises(TokenExpiredException):
        await service.refresh_access_token(expired_refresh_token)


async def test_refresh_access_token_rejects_a_malformed_token() -> None:
    service = TokenService()

    with pytest.raises(InvalidTokenException):
        await service.refresh_access_token("not-a-real-jwt")


# --- Router-level: POST /api/v2/auth/refresh ----------------------------------


def test_refresh_endpoint_returns_a_new_token_pair_for_a_valid_refresh_token(
    client: TestClient,
) -> None:
    subject = uuid.uuid4()
    refresh_token = create_refresh_token(subject)

    response = client.post(ENDPOINT, json={"refresh_token": refresh_token})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert "access_token" in body and "refresh_token" in body
    assert decode_token(body["access_token"])["sub"] == str(subject)


def test_refresh_endpoint_rejects_an_access_token_with_401_invalid_token(client: TestClient) -> None:
    access_token = create_access_token(uuid.uuid4())

    response = client.post(ENDPOINT, json={"refresh_token": access_token})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_refresh_endpoint_rejects_an_expired_refresh_token_with_401_token_expired(
    client: TestClient,
) -> None:
    expired_refresh_token = create_refresh_token(uuid.uuid4(), expires_days=-31)

    response = client.post(ENDPOINT, json={"refresh_token": expired_refresh_token})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_refresh_endpoint_rejects_a_malformed_token_with_401(client: TestClient) -> None:
    response = client.post(ENDPOINT, json={"refresh_token": "garbage"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_refresh_endpoint_requires_the_refresh_token_field(client: TestClient) -> None:
    response = client.post(ENDPOINT, json={})

    assert response.status_code == 422
