"""
Comprehensive Send OTP tests.

Uses fakes for the OTP repository and SMS provider (via FastAPI's
`dependency_overrides`) instead of a real Postgres/Supabase connection or
real Twilio calls — this sandboxed test environment has neither. This
still exercises the full `router -> AuthService -> OTPService ->
(repository, SMS provider)` path with the exact production wiring; only
the two outermost I/O boundaries are swapped for fakes.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from app.models.otp_challenge import OTPChallenge
from app.modules.auth.constants import OTP_RESEND_COOLDOWN_SECONDS
from app.modules.auth.dependencies.services import get_otp_repository, get_sms_provider
from app.modules.auth.exceptions import SMSDeliveryException
from app.modules.auth.providers.sms_provider import SMSProviderInterface
from app.modules.auth.repositories.otp_repository_interface import OTPRepositoryInterface
from app.utils.datetime import utc_now
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from loguru import logger

VALID_PHONE = "+919876543210"
ENDPOINT = "/api/v2/auth/phone/send-otp"


class FakeOTPRepository(OTPRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed repository."""

    def __init__(self) -> None:
        self.records: dict[str, OTPChallenge] = {}
        self.raise_on_access: Exception | None = None

    async def get_by_phone(self, phone_number: str) -> OTPChallenge | None:
        if self.raise_on_access is not None:
            raise self.raise_on_access
        return self.records.get(phone_number)

    async def upsert(self, phone_number: str, otp_hash: str, expires_at: datetime) -> OTPChallenge:
        if self.raise_on_access is not None:
            raise self.raise_on_access

        now = utc_now()
        existing = self.records.get(phone_number)
        if existing is not None:
            existing.otp_hash = otp_hash
            existing.expires_at = expires_at
            existing.attempts = 0
            existing.updated_at = now
            return existing

        challenge = OTPChallenge(
            phone_number=phone_number, otp_hash=otp_hash, expires_at=expires_at, attempts=0
        )
        challenge.created_at = now
        challenge.updated_at = now
        self.records[phone_number] = challenge
        return challenge

    async def increment_attempts(self, phone_number: str) -> int:
        challenge = self.records[phone_number]
        challenge.attempts += 1
        return challenge.attempts

    async def delete_by_phone(self, phone_number: str) -> None:
        self.records.pop(phone_number, None)


class FakeSMSProvider(SMSProviderInterface):
    """Records every message it was asked to send instead of calling a real provider."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.should_fail = False

    async def send(self, phone_number: str, message: str) -> None:
        if self.should_fail:
            raise SMSDeliveryException()
        self.sent.append((phone_number, message))


@pytest.fixture
def fake_repository() -> FakeOTPRepository:
    return FakeOTPRepository()


@pytest.fixture
def fake_sms_provider() -> FakeSMSProvider:
    return FakeSMSProvider()


@pytest.fixture
def wired_client(
    client: TestClient, fake_repository: FakeOTPRepository, fake_sms_provider: FakeSMSProvider
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_otp_repository] = lambda: fake_repository
    client.app.dependency_overrides[get_sms_provider] = lambda: fake_sms_provider
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_otp_repository, None)
        client.app.dependency_overrides.pop(get_sms_provider, None)


# --- Happy path --------------------------------------------------------------


def test_send_otp_success(
    wired_client: TestClient, fake_repository: FakeOTPRepository, fake_sms_provider: FakeSMSProvider
) -> None:
    response = wired_client.post(ENDPOINT, json={"phone": VALID_PHONE})

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "OTP sent successfully."}


def test_send_otp_persists_a_hashed_otp_never_the_plaintext(
    wired_client: TestClient,
    fake_repository: FakeOTPRepository,
    fake_sms_provider: FakeSMSProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.modules.auth.services.otp_service.generate_otp_code", lambda *a, **k: "123456")

    response = wired_client.post(ENDPOINT, json={"phone": VALID_PHONE})
    assert response.status_code == 200

    stored = fake_repository.records[VALID_PHONE]
    assert stored.otp_hash != "123456"
    assert PasswordHasher().verify(stored.otp_hash, "123456") is True
    assert stored.attempts == 0


def test_send_otp_never_returns_the_otp_in_the_response(
    wired_client: TestClient,
    fake_repository: FakeOTPRepository,
    fake_sms_provider: FakeSMSProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.modules.auth.services.otp_service.generate_otp_code", lambda *a, **k: "654321")

    response = wired_client.post(ENDPOINT, json={"phone": VALID_PHONE})

    assert "654321" not in response.text
    assert set(response.json().keys()) == {"success", "message"}


def test_send_otp_dispatches_via_the_sms_provider(
    wired_client: TestClient, fake_repository: FakeOTPRepository, fake_sms_provider: FakeSMSProvider
) -> None:
    response = wired_client.post(ENDPOINT, json={"phone": VALID_PHONE})

    assert response.status_code == 200
    assert len(fake_sms_provider.sent) == 1
    sent_phone, sent_message = fake_sms_provider.sent[0]
    assert sent_phone == VALID_PHONE
    assert "verification code" in sent_message


def test_send_otp_never_logs_the_otp_code(
    wired_client: TestClient,
    fake_repository: FakeOTPRepository,
    fake_sms_provider: FakeSMSProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.modules.auth.services.otp_service.generate_otp_code", lambda *a, **k: "999888")
    captured: list[str] = []
    sink_id = logger.add(lambda message: captured.append(str(message)), level="TRACE")
    try:
        response = wired_client.post(ENDPOINT, json={"phone": VALID_PHONE})
    finally:
        logger.remove(sink_id)

    assert response.status_code == 200
    assert "999888" not in "".join(captured)


# --- Validation ----------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_phone",
    ["", "not-a-phone", "9876543210", "+0123456789", "+1234", "12345678901"],
)
def test_send_otp_rejects_invalid_phone_numbers(wired_client: TestClient, invalid_phone: str) -> None:
    response = wired_client.post(ENDPOINT, json={"phone": invalid_phone})
    assert response.status_code == 422


def test_send_otp_rejects_missing_phone_field(wired_client: TestClient) -> None:
    response = wired_client.post(ENDPOINT, json={})
    assert response.status_code == 422


def test_send_otp_normalizes_formatting_before_validating(
    wired_client: TestClient, fake_sms_provider: FakeSMSProvider
) -> None:
    response = wired_client.post(ENDPOINT, json={"phone": "+91 98765-43210"})
    assert response.status_code == 200
    assert fake_sms_provider.sent[0][0] == "+919876543210"


# --- Rate limiting / cooldown ------------------------------------------------------


def test_send_otp_rate_limited_within_cooldown(
    wired_client: TestClient, fake_repository: FakeOTPRepository
) -> None:
    first = wired_client.post(ENDPOINT, json={"phone": VALID_PHONE})
    assert first.status_code == 200

    second = wired_client.post(ENDPOINT, json={"phone": VALID_PHONE})
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"


def test_send_otp_allowed_after_cooldown_expires(
    wired_client: TestClient, fake_repository: FakeOTPRepository
) -> None:
    first = wired_client.post(ENDPOINT, json={"phone": VALID_PHONE})
    assert first.status_code == 200

    # Simulate the cooldown window having already elapsed.
    stale_time = utc_now() - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS + 5)
    fake_repository.records[VALID_PHONE].updated_at = stale_time

    second = wired_client.post(ENDPOINT, json={"phone": VALID_PHONE})
    assert second.status_code == 200


# --- Failure handling --------------------------------------------------------------


def test_send_otp_provider_failure_returns_500(
    wired_client: TestClient, fake_sms_provider: FakeSMSProvider
) -> None:
    fake_sms_provider.should_fail = True

    response = wired_client.post(ENDPOINT, json={"phone": VALID_PHONE})

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "SMS_DELIVERY_FAILED"
    assert body["success"] is False


def test_send_otp_repository_failure_returns_generic_500_without_leaking_details(
    wired_client: TestClient, fake_repository: FakeOTPRepository
) -> None:
    fake_repository.raise_on_access = RuntimeError("connection to db exploded: secret_internal_detail")

    # `raise_server_exceptions=False` here because this test specifically
    # verifies production behavior (the global catch-all handler converting
    # an unexpected exception into a generic 500) — the shared `client`
    # fixture leaves the default `True` so *other* tests still surface a
    # real traceback on an unintended bug instead of silently passing.
    with TestClient(wired_client.app, raise_server_exceptions=False) as non_raising_client:
        response = non_raising_client.post(ENDPOINT, json={"phone": VALID_PHONE})

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "secret_internal_detail" not in response.text
