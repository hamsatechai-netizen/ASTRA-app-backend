"""
Profile module tests: fetch and update.

Uses a fake `ProfileRepositoryInterface` and a fake `UserRepositoryInterface`
(via FastAPI's `dependency_overrides`) instead of a real Postgres/Supabase
connection — same convention as `test_sessions.py`. Requests carry a real
JWT access token (via `create_access_token`), so `get_current_athlete`'s
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
from app.modules.profile.dependencies.services import get_profile_repository
from app.modules.profile.repositories.profile_repository_interface import ProfileRepositoryInterface
from fastapi.testclient import TestClient

PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"


def _profile_endpoint(athlete_id: str) -> str:
    return f"/api/mobile/athletes/{athlete_id}/profile"


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by profile tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by profile tests.")


class FakeProfileRepository(ProfileRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed profile repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def update_fields(
        self,
        athlete: HamsaTechAthlete,
        *,
        athlete_name: str | None = None,
        weapon_specialization: str | None = None,
        experience_level: str | None = None,
        goal_30_day: str | None = None,
        goal_6_month: str | None = None,
    ) -> HamsaTechAthlete:
        if athlete_name is not None:
            athlete.athlete_name = athlete_name
        if weapon_specialization is not None:
            athlete.weapon_specialization = weapon_specialization
        if experience_level is not None:
            athlete.experience_level = experience_level
        if goal_30_day is not None:
            athlete.goal_30_day = goal_30_day
        if goal_6_month is not None:
            athlete.goal_6_month = goal_6_month
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
def fake_profile_repository() -> FakeProfileRepository:
    repository = FakeProfileRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(
        athlete_id=ATHLETE_ID,
        contact_number=PHONE_NUMBER,
        athlete_name="Jane Doe",
        date_of_birth=date(2005, 4, 12),
        gender="Female",
        weapon_specialization="10m Air Rifle",
        experience_level="1 - 2 Years (Intermediate)",
        goal_30_day="Improve stance stability",
        goal_6_month="Qualify for nationals",
    )
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_profile_repository: FakeProfileRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_profile_repository] = lambda: fake_profile_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_profile_repository, None)


# --- GET /api/mobile/athletes/{athlete_id}/profile ---------------------------------


def test_get_profile_success(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.get(_profile_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["athlete_id"] == ATHLETE_ID
    assert body["athlete_name"] == "Jane Doe"
    assert body["date_of_birth"] == "2005-04-12"
    assert body["gender"] == "Female"
    assert body["sport_domain"] == "10m Air Rifle"
    assert body["experience_level"] == "1 - 2 Years (Intermediate)"
    assert body["goal_30"] == "Improve stance stability"
    assert body["goal_6_month"] == "Qualify for nationals"
    # Age is computed from date_of_birth, not stored — sanity-check it's a
    # plausible whole number rather than pinning an exact value that would
    # need updating every year this test suite runs.
    assert isinstance(body["age"], int)
    assert body["age"] >= 19

    # Never leak security/internal fields.
    for forbidden_key in ("password", "otp", "token", "jwt", "service_role", "contact_number"):
        assert forbidden_key not in body


def test_get_profile_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.get(_profile_endpoint(ATHLETE_ID))
    assert response.status_code == 401


def test_get_profile_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.get(
        _profile_endpoint(ATHLETE_ID), headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_get_profile_rejects_refresh_token_used_as_access_token(
    wired_client: TestClient, user_id: uuid.UUID
) -> None:
    refresh_token = create_refresh_token(user_id)
    response = wired_client.get(
        _profile_endpoint(ATHLETE_ID), headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert response.status_code == 401


def test_get_profile_rejects_mismatched_athlete_id(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.get(_profile_endpoint(OTHER_ATHLETE_ID), headers=auth_headers)
    assert response.status_code == 403


def test_get_profile_athlete_not_found(
    wired_client: TestClient, auth_headers: dict[str, str], fake_profile_repository: FakeProfileRepository
) -> None:
    fake_profile_repository.athletes.pop(PHONE_NUMBER)

    response = wired_client.get(_profile_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


def test_get_profile_handles_unset_fields(
    wired_client: TestClient, auth_headers: dict[str, str], fake_profile_repository: FakeProfileRepository
) -> None:
    fake_profile_repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(
        athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER
    )

    response = wired_client.get(_profile_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["athlete_name"] is None
    assert body["date_of_birth"] is None
    assert body["age"] is None
    assert body["sport_domain"] is None
    assert body["goal_30"] is None


# --- PUT /api/mobile/athletes/{athlete_id}/profile ----------------------------------


def test_update_profile_success(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_profile_repository: FakeProfileRepository,
) -> None:
    response = wired_client.put(
        _profile_endpoint(ATHLETE_ID),
        json={
            "fullName": "Jane A. Doe",
            "discipline": "25m Pistol",
            "experienceLevel": "3+ Years (Advanced)",
            "goal30Days": "Tighten grouping",
            "goal6Months": "Break personal record",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    # Response reflects the update immediately.
    assert body["athlete_name"] == "Jane A. Doe"
    assert body["sport_domain"] == "25m Pistol"
    assert body["experience_level"] == "3+ Years (Advanced)"
    assert body["goal_30"] == "Tighten grouping"
    assert body["goal_6_month"] == "Break personal record"

    # The update actually persisted on the underlying row, not just the response.
    persisted = fake_profile_repository.athletes[PHONE_NUMBER]
    assert persisted.athlete_name == "Jane A. Doe"
    assert persisted.weapon_specialization == "25m Pistol"
    assert persisted.experience_level == "3+ Years (Advanced)"
    assert persisted.goal_30_day == "Tighten grouping"
    assert persisted.goal_6_month == "Break personal record"


def test_update_profile_is_partial_and_ignores_age(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_profile_repository: FakeProfileRepository,
) -> None:
    """Only the sent fields change; `age` is accepted but never persisted or reflected as stored."""
    response = wired_client.put(
        _profile_endpoint(ATHLETE_ID),
        json={"goal30Days": "New 30-day goal", "age": 21},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["goal_30"] == "New 30-day goal"
    # Untouched fields are unchanged.
    assert body["athlete_name"] == "Jane Doe"
    assert body["sport_domain"] == "10m Air Rifle"
    assert body["goal_6_month"] == "Qualify for nationals"
    # date_of_birth (and therefore the computed age) is untouched by the `age` field.
    assert body["date_of_birth"] == "2005-04-12"


def test_update_profile_rejects_mismatched_athlete_id(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_profile_repository: FakeProfileRepository,
) -> None:
    response = wired_client.put(
        _profile_endpoint(OTHER_ATHLETE_ID), json={"fullName": "Someone Else"}, headers=auth_headers
    )

    assert response.status_code == 403
    # The real athlete's row must remain untouched.
    assert fake_profile_repository.athletes[PHONE_NUMBER].athlete_name == "Jane Doe"


def test_update_profile_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.put(_profile_endpoint(ATHLETE_ID), json={"fullName": "Someone"})
    assert response.status_code == 401


def test_update_profile_athlete_not_found(
    wired_client: TestClient, auth_headers: dict[str, str], fake_profile_repository: FakeProfileRepository
) -> None:
    fake_profile_repository.athletes.pop(PHONE_NUMBER)

    response = wired_client.put(
        _profile_endpoint(ATHLETE_ID), json={"fullName": "Someone"}, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


def test_update_profile_rejects_invalid_input(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.put(
        _profile_endpoint(ATHLETE_ID),
        json={"fullName": ""},  # violates min_length=1
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_profile_rejects_out_of_range_age(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.put(_profile_endpoint(ATHLETE_ID), json={"age": 999}, headers=auth_headers)
    assert response.status_code == 422
