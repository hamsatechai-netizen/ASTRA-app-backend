"""
Real-PostgreSQL regression test for OTP brute-force protection.

Proves that a wrong code's attempt increment survives the request-level rollback
that follows `InvalidOTPException` (it did not before: the increment was only
flushed into the request session, which `get_db` then rolled back, so the
five-attempt lockout never engaged).

Runs ONLY when `ASTRA_INTEGRATION_DB_URL` is set, points at a *local* database
(127.0.0.1 / localhost) and equals `DATABASE_URL`; otherwise the whole module is
skipped so the default unit suite stays hermetic. It can never target a remote
host. Every row it creates is phone-scoped synthetic data that it deletes again.

    DATABASE_URL=postgresql+asyncpg://astra_smoke@127.0.0.1:55432/astra_smoke \\
    ASTRA_INTEGRATION_DB_URL=$DATABASE_URL DATABASE_SSL_REQUIRED=false \\
    pytest tests/integration/test_otp_lockout_postgres.py
"""

import asyncio
import os
import re
import secrets
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit

import asyncpg
import pytest
from app.modules.auth.constants import OTP_MAX_VERIFICATION_ATTEMPTS
from app.modules.auth.dependencies.services import get_sms_provider
from app.modules.auth.providers.sms_provider import SMSProviderInterface
from fastapi.testclient import TestClient

INTEGRATION_URL = os.environ.get("ASTRA_INTEGRATION_DB_URL", "")
_LOCAL_URL = re.compile(r"^postgresql\+asyncpg://[^@/]+@(127\.0\.0\.1|localhost):\d+/\w+$")

pytestmark = pytest.mark.skipif(
    not _LOCAL_URL.match(INTEGRATION_URL) or os.environ.get("DATABASE_URL") != INTEGRATION_URL,
    reason="requires ASTRA_INTEGRATION_DB_URL pointing at a LOCAL database and equal to DATABASE_URL",
)

SEND = "/api/v2/auth/phone/send-otp"
VERIFY = "/api/v2/auth/phone/verify-otp"


def _db_args() -> dict[str, Any]:
    parts = urlsplit(INTEGRATION_URL.replace("postgresql+asyncpg://", "postgresql://"))
    return {
        "host": parts.hostname,
        "port": parts.port,
        "user": parts.username,
        "password": parts.password,
        "database": parts.path.lstrip("/"),
    }


def db(query: str, *args: Any) -> Any:
    """Run one statement on the LOCAL integration database over a raw asyncpg connection."""

    async def _run() -> Any:
        connection = await asyncpg.connect(**_db_args())
        try:
            return await connection.fetchval(query, *args)
        finally:
            await connection.close()

    return asyncio.run(_run())


def attempts_of(phone: str) -> int | None:
    return db("SELECT attempts FROM public.otp_challenges WHERE phone_number = $1", phone)


def challenge_exists(phone: str) -> bool:
    return bool(db("SELECT count(*) FROM public.otp_challenges WHERE phone_number = $1", phone))


def clear_resend_cooldown(phone: str) -> None:
    statement = (
        "UPDATE public.otp_challenges SET updated_at = now() - interval '1 hour' WHERE phone_number = $1"
    )
    db(statement, phone)


def expire_challenge(phone: str) -> None:
    statement = (
        "UPDATE public.otp_challenges SET expires_at = now() - interval '1 minute' WHERE phone_number = $1"
    )
    db(statement, phone)


class CapturingSMSProvider(SMSProviderInterface):
    """Captures the code from the message body; nothing ever leaves the process."""

    def __init__(self, store: dict[str, str]) -> None:
        self._store = store

    async def send(self, phone_number: str, message: str) -> None:
        match = re.search(r"\b(\d{6})\b", message)
        self._store[phone_number] = match.group(1) if match else ""


@pytest.fixture(scope="module", autouse=True)
def _engine_is_local() -> None:
    from app.database.session import engine

    assert engine.url.host in ("127.0.0.1", "localhost") and engine.url.database == _db_args()["database"]


@pytest.fixture
def phone() -> Iterator[str]:
    number = f"+91999991{secrets.randbelow(10_000):04d}"
    yield number
    db(
        "DELETE FROM hamsatech.athlete_physiology WHERE athlete_id IN "
        "(SELECT athlete_id FROM hamsatech.athletes WHERE contact_number = $1)",
        number,
    )
    db("DELETE FROM hamsatech.athletes WHERE contact_number = $1", number)
    db("DELETE FROM hamsatech.users WHERE phone_number = $1", number)
    db("DELETE FROM public.otp_challenges WHERE phone_number = $1", number)


@pytest.fixture
def otp_client(client: TestClient) -> Iterator[tuple[TestClient, dict[str, str]]]:
    codes: dict[str, str] = {}
    client.app.dependency_overrides[get_sms_provider] = lambda: CapturingSMSProvider(codes)
    try:
        yield client, codes
    finally:
        client.app.dependency_overrides.pop(get_sms_provider, None)


def _send(client: TestClient, phone: str) -> None:
    assert client.post(SEND, json={"phone": phone}).status_code == 200


def _verify(client: TestClient, phone: str, code: str) -> Any:
    return client.post(VERIFY, json={"phone_number": phone, "otp_code": code})


def _wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


def test_wrong_otp_increments_attempts_despite_request_rollback(
    otp_client: tuple[TestClient, dict[str, str]], phone: str
) -> None:
    client, codes = otp_client
    _send(client, phone)
    assert attempts_of(phone) == 0

    response = _verify(client, phone, _wrong(codes[phone]))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_OTP"
    assert attempts_of(phone) == 1  # survived the rollback of the failed request


def test_five_wrong_attempts_lock_out_the_sixth_and_the_correct_code(
    otp_client: tuple[TestClient, dict[str, str]], phone: str
) -> None:
    client, codes = otp_client
    _send(client, phone)

    for expected_attempts in range(1, OTP_MAX_VERIFICATION_ATTEMPTS + 1):
        response = _verify(client, phone, _wrong(codes[phone]))
        assert response.status_code == 400
        assert attempts_of(phone) == expected_attempts

    sixth = _verify(client, phone, _wrong(codes[phone]))
    assert sixth.status_code == 429
    assert sixth.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"

    correct = _verify(client, phone, codes[phone])
    assert correct.status_code == 429  # the correct code cannot bypass the lockout
    assert correct.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    assert challenge_exists(phone)  # not consumed
    assert attempts_of(phone) == OTP_MAX_VERIFICATION_ATTEMPTS  # a blocked attempt does not count further


def test_fresh_challenge_resets_attempts_and_correct_code_consumes_it(
    otp_client: tuple[TestClient, dict[str, str]], phone: str
) -> None:
    client, codes = otp_client
    _send(client, phone)
    for _ in range(OTP_MAX_VERIFICATION_ATTEMPTS):
        _verify(client, phone, _wrong(codes[phone]))
    assert _verify(client, phone, codes[phone]).status_code == 429

    clear_resend_cooldown(phone)  # local synthetic row: skip the 60 s wait
    _send(client, phone)
    assert attempts_of(phone) == 0  # fresh challenge, counter reset

    response = _verify(client, phone, codes[phone])

    assert response.status_code == 200
    body = response.json()
    assert body["is_new_user"] is True and body["next_step"] == "ONBOARDING_STEP_1"
    assert not challenge_exists(phone)  # consumed on success
    athlete_id = db("SELECT athlete_id FROM hamsatech.athletes WHERE contact_number = $1", phone)
    linked_uid = db("SELECT uid FROM hamsatech.users WHERE phone_number = $1", phone)
    assert linked_uid == athlete_id  # Blocker A linkage intact


def test_expired_and_missing_challenge_behaviour_unchanged(
    otp_client: tuple[TestClient, dict[str, str]], phone: str
) -> None:
    client, codes = otp_client
    missing = _verify(client, phone, "123456")
    assert missing.status_code == 400 and missing.json()["error"]["code"] == "INVALID_OTP"

    _send(client, phone)
    expire_challenge(phone)
    expired = _verify(client, phone, codes[phone])
    assert expired.status_code == 400 and expired.json()["error"]["code"] == "OTP_EXPIRED"
    assert attempts_of(phone) == 0  # expiry is not an attempt
    assert challenge_exists(phone)
