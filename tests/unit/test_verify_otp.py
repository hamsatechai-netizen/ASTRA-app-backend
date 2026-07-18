"""
Comprehensive Verify OTP tests.

Uses fakes for the OTP repository, user repository, athlete-profile
repository, and SMS provider (via FastAPI's `dependency_overrides`) —
this never touches the real `hamsatech.users`/`hamsatech.athletes`
tables, which hold real production data. Exercises the full
`router -> AuthService -> (OTPService, UserService, TokenService)` path
with the exact production wiring; only the repository/provider I/O
boundaries are swapped for fakes.
"""

import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta

import jwt
import pytest
from app.config.settings import get_settings
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.models.otp_challenge import OTPChallenge
from app.modules.auth.constants import JWT_ALGORITHM, OTP_MAX_VERIFICATION_ATTEMPTS
from app.modules.auth.dependencies.services import (
    get_athlete_profile_repository,
    get_otp_repository,
    get_user_repository,
)
from app.modules.auth.repositories.athlete_profile_repository_interface import (
    AthleteProfileRepositoryInterface,
)
from app.modules.auth.repositories.otp_repository_interface import OTPRepositoryInterface
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import hash_otp
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

VALID_PHONE = "+919876543210"
VALID_OTP = "123456"
ENDPOINT = "/api/v2/auth/phone/verify-otp"


class FakeOTPRepository(OTPRepositoryInterface):
    def __init__(self) -> None:
        self.records: dict[str, OTPChallenge] = {}

    async def get_by_phone(self, phone_number: str) -> OTPChallenge | None:
        return self.records.get(phone_number)

    async def upsert(self, phone_number: str, otp_hash: str, expires_at: datetime) -> OTPChallenge:
        challenge = OTPChallenge(
            phone_number=phone_number, otp_hash=otp_hash, expires_at=expires_at, attempts=0
        )
        self.records[phone_number] = challenge
        return challenge

    async def increment_attempts(self, phone_number: str) -> int:
        challenge = self.records[phone_number]
        challenge.attempts += 1
        return challenge.attempts

    async def delete_by_phone(self, phone_number: str) -> None:
        self.records.pop(phone_number, None)

    def seed(
        self, phone_number: str, otp_code: str, *, attempts: int = 0, expires_in_seconds: int = 300
    ) -> None:
        self.records[phone_number] = OTPChallenge(
            phone_number=phone_number,
            otp_hash=hash_otp(otp_code),
            expires_at=utc_now() + timedelta(seconds=expires_in_seconds),
            attempts=attempts,
        )


class FakeUserRepository(UserRepositoryInterface):
    def __init__(self) -> None:
        self.users: dict[str, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return self.users.get(phone_number)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return next((user for user in self.users.values() if user.id == user_id), None)

    async def create(self, phone_number: str) -> HamsaTechUser:
        user = HamsaTechUser(id=uuid.uuid4(), phone_number=phone_number)
        self.users[phone_number] = user
        return user

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        now = utc_now().replace(tzinfo=None)
        user.phone_verified_at = now
        user.last_login_at = now


class FakeAthleteProfileRepository(AthleteProfileRepositoryInterface):
    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}
        self._next_id = 1

    async def get_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def create_minimal(self, phone_number: str) -> HamsaTechAthlete:
        athlete = HamsaTechAthlete(athlete_id=f"ASA{self._next_id:03d}", contact_number=phone_number)
        self._next_id += 1
        self.athletes[phone_number] = athlete
        return athlete


@pytest.fixture
def fake_otp_repository() -> FakeOTPRepository:
    return FakeOTPRepository()


@pytest.fixture
def fake_user_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_athlete_repository() -> FakeAthleteProfileRepository:
    return FakeAthleteProfileRepository()


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_otp_repository] = lambda: fake_otp_repository
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_athlete_profile_repository] = lambda: fake_athlete_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_otp_repository, None)
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_athlete_profile_repository, None)


def _payload(phone: str = VALID_PHONE, otp: str = VALID_OTP) -> dict[str, str]:
    return {"phone_number": phone, "otp_code": otp}


# --- Happy path: new user, no athlete profile -> ONBOARDING_STEP_1 -----------------


def test_verify_otp_new_user_no_athlete_returns_onboarding_step_1(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["is_new_user"] is True
    assert body["next_step"] == "ONBOARDING_STEP_1"
    assert body["token_type"] == "bearer"
    assert "access_token" in body and "refresh_token" in body


def test_verify_otp_creates_athlete_profile_linked_by_phone(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    created = fake_athlete_repository.athletes[VALID_PHONE]
    assert created.contact_number == VALID_PHONE


# --- Happy path: existing athlete -> HOME -----------------------------------------


def test_verify_otp_existing_athlete_returns_home(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)
    fake_athlete_repository.athletes[VALID_PHONE] = HamsaTechAthlete(
        athlete_id="ASA999", contact_number=VALID_PHONE
    )

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    assert response.json()["next_step"] == "HOME"


def test_verify_otp_existing_user_is_new_user_false(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)
    existing_user = HamsaTechUser(id=uuid.uuid4(), phone_number=VALID_PHONE)
    fake_user_repository.users[VALID_PHONE] = existing_user

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["is_new_user"] is False
    assert body["user_id"] == str(existing_user.id)


def test_verify_otp_marks_phone_verified_and_updates_last_login(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    stored_user = fake_user_repository.users[VALID_PHONE]
    assert stored_user.phone_verified_at is not None
    assert stored_user.last_login_at is not None


def test_verify_otp_consumes_the_challenge(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    assert fake_otp_repository.records.get(VALID_PHONE) is None


def test_verify_otp_issues_a_valid_jwt_for_the_user(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    body = response.json()
    settings = get_settings()
    claims = jwt.decode(body["access_token"], settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    assert claims["sub"] == body["user_id"]
    assert claims["type"] == "access"


# --- Failure handling --------------------------------------------------------------


def test_verify_otp_no_challenge_returns_400(wired_client: TestClient) -> None:
    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_OTP"


def test_verify_otp_wrong_code_returns_400_and_increments_attempts(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload(otp="000000"))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_OTP"
    assert fake_otp_repository.records[VALID_PHONE].attempts == 1


def test_verify_otp_expired_returns_400(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP, expires_in_seconds=-10)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OTP_EXPIRED"


def test_verify_otp_too_many_attempts_returns_429(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP, attempts=OTP_MAX_VERIFICATION_ATTEMPTS)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"


def test_verify_otp_failed_verification_never_touches_user_or_athlete(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload(otp="000000"))

    assert response.status_code == 400
    assert fake_user_repository.users == {}
    assert fake_athlete_repository.athletes == {}


# --- Validation ----------------------------------------------------------------


def test_verify_otp_rejects_malformed_otp_code(wired_client: TestClient) -> None:
    response = wired_client.post(ENDPOINT, json=_payload(otp="abc"))
    assert response.status_code == 422


def test_verify_otp_rejects_malformed_phone_number(wired_client: TestClient) -> None:
    response = wired_client.post(ENDPOINT, json=_payload(phone="not-a-phone"))
    assert response.status_code == 422


# --- Swagger / OpenAPI --------------------------------------------------------------


def test_openapi_documents_auth_endpoints_and_schemas(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert "/api/v2/auth/phone/send-otp" in paths
    assert "/api/v2/auth/phone/verify-otp" in paths

    component_schemas = schema["components"]["schemas"]
    assert "SendOTPRequest" in component_schemas
    assert "VerifyOTPRequest" in component_schemas
    assert "AuthResponse" in component_schemas
    assert "OTPSentResponse" in component_schemas
