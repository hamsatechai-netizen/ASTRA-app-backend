"""
Bootstrap smoke tests.

Phase 1 ships no business logic, so there is nothing domain-specific to
test yet. These tests instead verify the architecture itself: the app
factory builds a valid FastAPI app, Swagger/OpenAPI is served, and the
security/observability middleware stack is actually applied.
"""

from fastapi.testclient import TestClient


def test_app_metadata(client: TestClient) -> None:
    assert client.app.title == "ASTRA Backend"


def test_openapi_schema_is_served(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "ASTRA Backend"


def test_swagger_ui_is_served(client: TestClient) -> None:
    response = client.get("/docs")
    assert response.status_code == 200


def test_redoc_is_served(client: TestClient) -> None:
    response = client.get("/redoc")
    assert response.status_code == 200


def test_security_headers_are_applied(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "strict-transport-security" in response.headers


def test_request_id_header_is_generated(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert "x-request-id" in response.headers


def test_unknown_route_returns_standard_error_envelope(client: TestClient) -> None:
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "HTTP_ERROR"
