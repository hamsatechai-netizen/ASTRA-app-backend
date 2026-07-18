"""
Comprehensive onboarding Step 1 tests.

Uses fakes for the user and onboarding repositories (via FastAPI's
`dependency_overrides`) instead of a real Postgres/Supabase connection —
this sandboxed test environment has neither. Requests carry a real JWT
access token (via `create_access_token`), so `get_current_athlete`'s
actual decode-and-lookup logic is exercised end-to-end, not stubbed out.
"""

import uuid
from collections.abc import Iterator
from datetime import date

import pytest
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token, create_refresh_token
from app.modules.onboarding.dependencies.services import get_onboarding_repository
from app.modules.onboarding.repositories.onboarding_repository_interface import (
    OnboardingRepositoryInterface,
)
from fastapi.testclient import TestClient

STATUS_ENDPOINT = "/api/v2/onboarding"
STEP_1_ENDPOINT = "/api/v2/onboarding/step-1"
PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"

VALID_STEP_1_BODY = {
    "fullName": "Jane Doe",
    "dateOfBirth": "2005-04-12",
    "gender": "Female",
    "city": "Mumbai",
}


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by onboarding tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by onboarding tests.")


class FakeOnboardingRepository(OnboardingRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed onboarding repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number

    async def get_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def save_step_1(
        self,
        athlete: HamsaTechAthlete,
        *,
        full_name: str,
        date_of_birth: date,
        gender: str,
        city: str,
    ) -> HamsaTechAthlete:
        athlete.athlete_name = full_name
        athlete.date_of_birth = date_of_birth
        athlete.gender = gender
        athlete.city = city
        athlete.current_onboarding_step = 2
        return athlete


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_user_repository(user_id: uuid.UUID) -> FakeUserRepository:
    repository = FakeUserRepository()
    repository.users[user_id] = HamsaTechUser(id=user_id, phone_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def fake_onboarding_repository() -> FakeOnboardingRepository:
    return FakeOnboardingRepository()


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_onboarding_repository: FakeOnboardingRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_onboarding_repository] = lambda: fake_onboarding_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_onboarding_repository, None)


def _existing_athlete(current_onboarding_step: int = 1) -> HamsaTechAthlete:
    return HamsaTechAthlete(
        athlete_id=ATHLETE_ID,
        contact_number=PHONE_NUMBER,
        current_onboarding_step=current_onboarding_step,
    )


# --- Authentication ------------------------------------------------------------


def test_get_onboarding_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.get(STATUS_ENDPOINT)
    assert response.status_code == 401


def test_get_onboarding_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.get(STATUS_ENDPOINT, headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_get_onboarding_rejects_refresh_token_used_as_access_token(
    wired_client: TestClient, user_id: uuid.UUID
) -> None:
    refresh_token = create_refresh_token(user_id)
    response = wired_client.get(STATUS_ENDPOINT, headers={"Authorization": f"Bearer {refresh_token}"})
    assert response.status_code == 401


def test_get_onboarding_rejects_unknown_user(wired_client: TestClient) -> None:
    token = create_access_token(uuid.uuid4())  # a user_id no fake repository knows about
    response = wired_client.get(STATUS_ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# --- GET /api/v2/onboarding ------------------------------------------------------


def test_get_onboarding_athlete_not_found(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.get(STATUS_ENDPOINT, headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


def test_get_onboarding_not_started_returns_step_1(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=1)

    response = wired_client.get(STATUS_ENDPOINT, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["athlete_id"] == ATHLETE_ID
    assert body["current_onboarding_step"] == 1
    assert body["is_onboarding_complete"] is False
    assert body["full_name"] is None
    assert body["date_of_birth"] is None
    assert body["gender"] is None
    assert body["city"] is None


def test_get_onboarding_reflects_saved_step_1_data(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    athlete = _existing_athlete(current_onboarding_step=2)
    athlete.athlete_name = "Jane Doe"
    athlete.date_of_birth = date(2005, 4, 12)
    athlete.gender = "Female"
    athlete.city = "Mumbai"
    fake_onboarding_repository.athletes[PHONE_NUMBER] = athlete

    response = wired_client.get(STATUS_ENDPOINT, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["current_onboarding_step"] == 2
    assert body["full_name"] == "Jane Doe"
    assert body["date_of_birth"] == "2005-04-12"
    assert body["gender"] == "Female"
    assert body["city"] == "Mumbai"


# --- PUT /api/v2/onboarding/step-1 ------------------------------------------------


def test_put_step_1_success(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=1)

    response = wired_client.put(STEP_1_ENDPOINT, json=VALID_STEP_1_BODY, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["current_onboarding_step"] == 2
    assert body["full_name"] == "Jane Doe"
    assert body["date_of_birth"] == "2005-04-12"
    assert body["gender"] == "Female"
    assert body["city"] == "Mumbai"

    saved = fake_onboarding_repository.athletes[PHONE_NUMBER]
    assert saved.athlete_name == "Jane Doe"
    assert saved.current_onboarding_step == 2


def test_put_step_1_does_not_create_a_new_athlete(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    response = wired_client.put(STEP_1_ENDPOINT, json=VALID_STEP_1_BODY, headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"
    assert PHONE_NUMBER not in fake_onboarding_repository.athletes


@pytest.mark.parametrize(
    "invalid_body",
    [
        {**VALID_STEP_1_BODY, "fullName": ""},
        {**VALID_STEP_1_BODY, "fullName": "   "},
        {**VALID_STEP_1_BODY, "dateOfBirth": "not-a-date"},
        {**VALID_STEP_1_BODY, "gender": "Alien"},
        {**VALID_STEP_1_BODY, "city": ""},
        {k: v for k, v in VALID_STEP_1_BODY.items() if k != "fullName"},
        {k: v for k, v in VALID_STEP_1_BODY.items() if k != "dateOfBirth"},
        {k: v for k, v in VALID_STEP_1_BODY.items() if k != "gender"},
        {k: v for k, v in VALID_STEP_1_BODY.items() if k != "city"},
    ],
)
def test_put_step_1_rejects_invalid_bodies(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    invalid_body: dict[str, str],
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete()

    response = wired_client.put(STEP_1_ENDPOINT, json=invalid_body, headers=auth_headers)

    assert response.status_code == 422


def test_put_step_1_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.put(STEP_1_ENDPOINT, json=VALID_STEP_1_BODY)
    assert response.status_code == 401
