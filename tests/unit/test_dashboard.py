"""
Dashboard module tests: home summary.

Uses a fake `DashboardRepositoryInterface` and a fake `UserRepositoryInterface`
(via FastAPI's `dependency_overrides`) instead of a real Postgres/Supabase
connection — same convention as `test_profile.py`/`test_sessions.py`.
Requests carry a real JWT access token (via `create_access_token`), so
`get_current_athlete`'s actual decode-and-lookup logic is exercised
end-to-end, not stubbed out.
"""

import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token, create_refresh_token
from app.modules.dashboard.dependencies.services import get_dashboard_repository
from app.modules.dashboard.repositories.dashboard_repository_interface import (
    DashboardRepositoryInterface,
)
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"


def _home_endpoint(athlete_id: str) -> str:
    return f"/api/mobile/athletes/{athlete_id}/home"


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by dashboard tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by dashboard tests.")


class FakeDashboardRepository(DashboardRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed dashboard repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number
        self.sessions_this_week: dict[str, int] = {}
        self.avg_scores: dict[str, float | None] = {}
        self.since_calls: list[datetime] = []

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def count_completed_sessions_since(self, athlete_id: str, since: datetime) -> int:
        self.since_calls.append(since)
        return self.sessions_this_week.get(athlete_id, 0)

    async def get_average_score_since(self, athlete_id: str, since: datetime) -> float | None:
        return self.avg_scores.get(athlete_id)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_user_repository(user_id: uuid.UUID) -> FakeUserRepository:
    repository = FakeUserRepository()
    repository.users[user_id] = HamsaTechUser(id=user_id, phone_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def fake_dashboard_repository() -> FakeDashboardRepository:
    repository = FakeDashboardRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(
        athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER, athlete_name="Jane Doe"
    )
    repository.sessions_this_week[ATHLETE_ID] = 3
    repository.avg_scores[ATHLETE_ID] = 87.5
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_dashboard_repository: FakeDashboardRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_dashboard_repository] = lambda: fake_dashboard_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_dashboard_repository, None)


# --- GET /api/mobile/athletes/{athlete_id}/home -------------------------------------


def test_get_home_success(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.get(_home_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["athlete_id"] == ATHLETE_ID
    assert body["athlete_name"] == "Jane Doe"
    assert body["sessions_this_week"] == 3
    assert body["weekly_avg_score"] == 87.5


def test_get_home_schema_has_no_extra_or_sensitive_fields(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.get(_home_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    # Exactly the four documented fields — no streak, no ai_insights, no
    # readiness/recovery/stress/steady, no fabricated metric of any kind.
    assert set(body.keys()) == {"athlete_id", "athlete_name", "sessions_this_week", "weekly_avg_score"}
    for forbidden_key in (
        "password",
        "otp",
        "token",
        "jwt",
        "service_role",
        "contact_number",
        "streak",
        "streak_days",
        "readiness",
        "recovery",
        "stress",
        "steady",
        "ai_insights",
    ):
        assert forbidden_key not in body


def test_get_home_no_score_yet_this_week_is_null_not_zero(
    wired_client: TestClient, auth_headers: dict[str, str], fake_dashboard_repository: FakeDashboardRepository
) -> None:
    fake_dashboard_repository.sessions_this_week[ATHLETE_ID] = 1
    fake_dashboard_repository.avg_scores[ATHLETE_ID] = None

    response = wired_client.get(_home_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["sessions_this_week"] == 1
    assert body["weekly_avg_score"] is None


def test_get_home_zero_sessions_this_week(
    wired_client: TestClient, auth_headers: dict[str, str], fake_dashboard_repository: FakeDashboardRepository
) -> None:
    fake_dashboard_repository.sessions_this_week[ATHLETE_ID] = 0
    fake_dashboard_repository.avg_scores[ATHLETE_ID] = None

    response = wired_client.get(_home_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["sessions_this_week"] == 0
    assert body["weekly_avg_score"] is None


def test_get_home_week_boundary_is_start_of_current_utc_week(
    wired_client: TestClient, auth_headers: dict[str, str], fake_dashboard_repository: FakeDashboardRepository
) -> None:
    wired_client.get(_home_endpoint(ATHLETE_ID), headers=auth_headers)

    assert len(fake_dashboard_repository.since_calls) == 1
    since = fake_dashboard_repository.since_calls[0]
    assert since.weekday() == 0  # Monday
    assert (since.hour, since.minute, since.second, since.microsecond) == (0, 0, 0, 0)
    assert since.tzinfo is None  # naive — matches Session.start_time's storage convention
    now_naive = utc_now().replace(tzinfo=None)
    assert since <= now_naive
    assert since >= now_naive - timedelta(days=7)


def test_get_home_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.get(_home_endpoint(ATHLETE_ID))
    assert response.status_code == 401


def test_get_home_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.get(
        _home_endpoint(ATHLETE_ID), headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_get_home_rejects_refresh_token_used_as_access_token(
    wired_client: TestClient, user_id: uuid.UUID
) -> None:
    refresh_token = create_refresh_token(user_id)
    response = wired_client.get(
        _home_endpoint(ATHLETE_ID), headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert response.status_code == 401


def test_get_home_rejects_mismatched_athlete_id(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.get(_home_endpoint(OTHER_ATHLETE_ID), headers=auth_headers)
    assert response.status_code == 403


def test_get_home_athlete_not_found(
    wired_client: TestClient, auth_headers: dict[str, str], fake_dashboard_repository: FakeDashboardRepository
) -> None:
    fake_dashboard_repository.athletes.pop(PHONE_NUMBER)

    response = wired_client.get(_home_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


def test_get_home_handles_unset_athlete_name(
    wired_client: TestClient, auth_headers: dict[str, str], fake_dashboard_repository: FakeDashboardRepository
) -> None:
    fake_dashboard_repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(
        athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER
    )

    response = wired_client.get(_home_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["athlete_name"] is None
