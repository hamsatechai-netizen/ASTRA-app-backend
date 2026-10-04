"""
Comprehensive academies-listing tests.

Uses fakes for the user and academy repositories (via FastAPI's
`dependency_overrides`) instead of a real Postgres/Supabase connection —
this sandboxed test environment has neither. Requests carry a real JWT
access token (via `create_access_token`), so `get_current_athlete`'s
actual decode-and-lookup logic is exercised end-to-end, not stubbed out.
"""

import uuid
from collections.abc import Iterator
from uuid import UUID

import pytest
from app.models.hamsatech_academy import HamsaTechAcademy
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_athlete_details import HamsaTechAthleteDetails
from app.models.hamsatech_user import HamsaTechUser
from app.modules.academies.dependencies.services import get_academy_repository
from app.modules.academies.repositories.academy_repository_interface import AcademyRepositoryInterface
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token
from app.modules.onboarding.dependencies.services import (
    get_athlete_details_repository,
    get_onboarding_repository,
)
from app.modules.onboarding.repositories.athlete_details_repository_interface import (
    AthleteDetailsRepositoryInterface,
)
from app.modules.onboarding.repositories.onboarding_repository_interface import (
    OnboardingRepositoryInterface,
)
from fastapi.testclient import TestClient

ACADEMIES_ENDPOINT = "/api/v2/academies"
STEP_2_ENDPOINT = "/api/v2/onboarding/step-2"
PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by academies tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by academies tests.")


class FakeAcademyRepository(AcademyRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed academy repository."""

    def __init__(self) -> None:
        self.academies: list[HamsaTechAcademy] = []

    async def get_all(self) -> list[HamsaTechAcademy]:
        return list(self.academies)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_user_repository(user_id: uuid.UUID) -> FakeUserRepository:
    repository = FakeUserRepository()
    repository.users[user_id] = HamsaTechUser(id=user_id, phone_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def fake_academy_repository() -> FakeAcademyRepository:
    return FakeAcademyRepository()


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_academy_repository: FakeAcademyRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_academy_repository] = lambda: fake_academy_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_academy_repository, None)


# --- Authentication ------------------------------------------------------------


def test_list_academies_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.get(ACADEMIES_ENDPOINT)
    assert response.status_code == 401


def test_list_academies_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.get(ACADEMIES_ENDPOINT, headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


# --- GET /api/v2/academies -----------------------------------------------------


def test_list_academies_returns_academies(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_academy_repository: FakeAcademyRepository,
) -> None:
    academy_id = uuid.uuid4()
    fake_academy_repository.academies.append(
        HamsaTechAcademy(academy_id=academy_id, academy_name="Arjun Sports Academy", location="Vizag")
    )

    response = wired_client.get(ACADEMIES_ENDPOINT, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {"academyId": str(academy_id), "academyName": "Arjun Sports Academy", "location": "Vizag"}
    ]


def test_list_academies_uuids_are_correct(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_academy_repository: FakeAcademyRepository,
) -> None:
    first_id, second_id = uuid.uuid4(), uuid.uuid4()
    fake_academy_repository.academies.extend(
        [
            HamsaTechAcademy(academy_id=first_id, academy_name="Academy A", location="City A"),
            HamsaTechAcademy(academy_id=second_id, academy_name="Academy B", location="City B"),
        ]
    )

    response = wired_client.get(ACADEMIES_ENDPOINT, headers=auth_headers)

    assert response.status_code == 200
    returned_ids = {UUID(item["academyId"]) for item in response.json()}
    assert returned_ids == {first_id, second_id}


def test_list_academies_response_contract_has_only_expected_keys(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_academy_repository: FakeAcademyRepository,
) -> None:
    fake_academy_repository.academies.append(
        HamsaTechAcademy(academy_id=uuid.uuid4(), academy_name="Academy A", location="City A")
    )

    response = wired_client.get(ACADEMIES_ENDPOINT, headers=auth_headers)

    assert response.status_code == 200
    assert set(response.json()[0].keys()) == {"academyId", "academyName", "location"}


def test_list_academies_location_can_be_null(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_academy_repository: FakeAcademyRepository,
) -> None:
    fake_academy_repository.academies.append(
        HamsaTechAcademy(academy_id=uuid.uuid4(), academy_name="Academy With No Location", location=None)
    )

    response = wired_client.get(ACADEMIES_ENDPOINT, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()[0]["location"] is None


def test_list_academies_returns_empty_array_not_404_when_none_exist(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.get(ACADEMIES_ENDPOINT, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


# --- Onboarding Step 2 can consume this response ------------------------------------


class _FakeOnboardingRepositoryForAcademyId(OnboardingRepositoryInterface):
    """Minimal onboarding-repository fake, just enough to exercise Step 2."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}

    async def get_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def save_step_1(self, athlete, **kwargs) -> HamsaTechAthlete:  # noqa: ANN001, ANN003
        raise NotImplementedError

    async def save_step_2(
        self, athlete: HamsaTechAthlete, *, discipline, experience_level, years_shooting, academy_id
    ) -> HamsaTechAthlete:
        athlete.weapon_specialization = discipline
        athlete.experience_level = experience_level
        athlete.years_shooting = years_shooting
        athlete.academy_id = academy_id
        athlete.current_onboarding_step = 3
        return athlete

    async def save_step_3(self, athlete, **kwargs) -> HamsaTechAthlete:  # noqa: ANN001, ANN003
        raise NotImplementedError

    async def advance_onboarding_step(self, athlete: HamsaTechAthlete, step: int) -> HamsaTechAthlete:
        athlete.current_onboarding_step = step
        return athlete


class _FakeAthleteDetailsRepositoryForAcademyId(AthleteDetailsRepositoryInterface):
    """Unused by Step 2, present only to satisfy `OnboardingService`'s constructor."""

    async def get_by_athlete_id(self, athlete_id: str) -> HamsaTechAthleteDetails | None:
        return None

    async def create(self, athlete_id: str, **kwargs) -> HamsaTechAthleteDetails:  # noqa: ANN003
        raise NotImplementedError

    async def update(self, details, **kwargs) -> HamsaTechAthleteDetails:  # noqa: ANN001, ANN003
        raise NotImplementedError

    async def create_step_5(self, athlete_id: str, **kwargs) -> HamsaTechAthleteDetails:  # noqa: ANN003
        raise NotImplementedError

    async def update_step_5(self, details, **kwargs) -> HamsaTechAthleteDetails:  # noqa: ANN001, ANN003
        raise NotImplementedError

    async def create_step_6(self, athlete_id: str, **kwargs) -> HamsaTechAthleteDetails:  # noqa: ANN003
        raise NotImplementedError

    async def update_step_6(self, details, **kwargs) -> HamsaTechAthleteDetails:  # noqa: ANN001, ANN003
        raise NotImplementedError


def test_onboarding_step_2_accepts_an_academy_id_from_the_academies_endpoint(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_academy_repository: FakeAcademyRepository,
) -> None:
    academy_id = uuid.uuid4()
    fake_academy_repository.academies.append(
        HamsaTechAcademy(academy_id=academy_id, academy_name="Arjun Sports Academy", location="Vizag")
    )
    academies_response = wired_client.get(ACADEMIES_ENDPOINT, headers=auth_headers)
    assert academies_response.status_code == 200
    picked_academy_id = academies_response.json()[0]["academyId"]

    onboarding_repository = _FakeOnboardingRepositoryForAcademyId()
    onboarding_repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(
        athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER, current_onboarding_step=2
    )
    wired_client.app.dependency_overrides[get_onboarding_repository] = lambda: onboarding_repository
    wired_client.app.dependency_overrides[get_athlete_details_repository] = (
        lambda: _FakeAthleteDetailsRepositoryForAcademyId()
    )
    try:
        step_2_response = wired_client.put(
            STEP_2_ENDPOINT,
            json={
                "discipline": "10m Air Rifle",
                "experienceLevel": "1 - 2 Years (Intermediate)",
                "yearsShooting": 2,
                "academyId": picked_academy_id,
            },
            headers=auth_headers,
        )
    finally:
        wired_client.app.dependency_overrides.pop(get_onboarding_repository, None)
        wired_client.app.dependency_overrides.pop(get_athlete_details_repository, None)

    assert step_2_response.status_code == 200
    assert step_2_response.json()["academy_id"] == picked_academy_id
