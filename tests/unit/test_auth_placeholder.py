"""
Auth module placeholder tests.

Send OTP is now fully implemented (see `test_send_otp.py`); Verify OTP
remains an unimplemented placeholder — these tests confirm it still
always returns HTTP 501 wrapped in the project's standard error envelope,
and that both endpoints' schemas are correctly published in the OpenAPI
schema (i.e. they render in Swagger).
"""

from fastapi.testclient import TestClient

VALID_PHONE = "+14155552671"
VALID_OTP = "123456"


def test_verify_otp_returns_501(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/phone/verify-otp",
        json={"phone_number": VALID_PHONE, "otp_code": VALID_OTP},
    )
    assert response.status_code == 501
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "HTTP_ERROR"


def test_verify_otp_rejects_malformed_otp_code(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/phone/verify-otp",
        json={"phone_number": VALID_PHONE, "otp_code": "abc"},
    )
    assert response.status_code == 422


def test_openapi_documents_auth_endpoints_and_schemas(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert "/api/v1/auth/phone/send-otp" in paths
    assert "/api/v1/auth/phone/verify-otp" in paths

    component_schemas = schema["components"]["schemas"]
    assert "SendOTPRequest" in component_schemas
    assert "VerifyOTPRequest" in component_schemas
    assert "AuthResponse" in component_schemas
    assert "OTPSentResponse" in component_schemas
