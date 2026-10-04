"""
Baseline module tests: physiological baseline (resting HR) capture and
read-back.

Uses a fake `BaselineRepositoryInterface` and a fake `UserRepositoryInterface`
(via FastAPI's `dependency_overrides`) instead of a real Postgres/Supabase
connection — same convention as `test_streak.py`/`test_checkin.py`.
Requests carry a real JWT access token (via `create_access_token`), so
`get_current_athlete`'s actual decode-and-lookup logic is exercised
end-to-end, not stubbed out.

Test matrix: successful create, successful read-back, authentication
failure, athlete ownership mismatch, invalid resting HR, no existing
baseline row, and latest-row selection when multiple rows exist.
"""

import uuid
from collections.abc import Iterator
from datetime import date, datetime, timedelta

import pytest
from app.models.athlete_physiology import AthletePhysiology
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token
from app.modules.baseline.dependencies.services import get_baseline_repository
from app.modules.baseline.repositories.baseline_repository_interface import BaselineRepositoryInterface
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"


def _baseline_endpoint(athlete_id: str) -> str:
    return f"/api/mobile/athletes/{athlete_id}/baseline"


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by baseline tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by baseline tests.")


class FakeBaselineRepository(BaselineRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed baseline repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number
        self.rows_by_athlete: dict[str, list[AthletePhysiology]] = {}

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def create_baseline(
        self, *, athlete_id: str, resting_heart_rate: int, recorded_date: date
    ) -> AthletePhysiology:
        row = AthletePhysiology(
            physiology_id=uuid.uuid4(),
            athlete_id=athlete_id,
            session_id=None,
            recorded_date=recorded_date,
            resting_heart_rate=resting_heart_rate,
            created_at=utc_now().replace(tzinfo=None),
        )
        self.rows_by_athlete.setdefault(athlete_id, []).append(row)
        return row

    async def get_latest_baseline(self, athlete_id: str) -> AthletePhysiology | None:
        rows = self.rows_by_athlete.get(athlete_id, [])
        if not rows:
            return None
        return max(rows, key=lambda r: r.created_at or datetime.min)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_user_repository(user_id: uuid.UUID) -> FakeUserRepository:
    repository = FakeUserRepository()
    repository.users[user_id] = HamsaTechUser(id=user_id, phone_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def fake_baseline_repository() -> FakeBaselineRepository:
    repository = FakeBaselineRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_baseline_repository: FakeBaselineRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_baseline_repository] = lambda: fake_baseline_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_baseline_repository, None)


def test_create_baseline_success(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.post(
        _baseline_endpoint(ATHLETE_ID), json={"resting_hr": 62}, headers=auth_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["athlete_id"] == ATHLETE_ID
    assert body["resting_heart_rate"] == 62
    assert body["session_id"] is None
    assert body["recorded_date"] == utc_now().date().isoformat()
    assert body["created_at"] is not None


def test_get_baseline_reads_back_created_row(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    wired_client.post(_baseline_endpoint(ATHLETE_ID), json={"resting_hr": 58}, headers=auth_headers)

    response = wired_client.get(_baseline_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["athlete_id"] == ATHLETE_ID
    assert body["resting_heart_rate"] == 58


def test_create_baseline_without_token_is_unauthorized(wired_client: TestClient) -> None:
    response = wired_client.post(_baseline_endpoint(ATHLETE_ID), json={"resting_hr": 60})

    assert response.status_code == 401


def test_get_baseline_without_token_is_unauthorized(wired_client: TestClient) -> None:
    response = wired_client.get(_baseline_endpoint(ATHLETE_ID))

    assert response.status_code == 401


def test_create_baseline_for_other_athlete_is_forbidden(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.post(
        _baseline_endpoint(OTHER_ATHLETE_ID), json={"resting_hr": 60}, headers=auth_headers
    )

    assert response.status_code == 403


def test_get_baseline_for_other_athlete_is_forbidden(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.get(_baseline_endpoint(OTHER_ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 403


@pytest.mark.parametrize("resting_hr", [0, -5, 301])
def test_create_baseline_rejects_invalid_resting_hr(
    wired_client: TestClient, auth_headers: dict[str, str], resting_hr: int
) -> None:
    response = wired_client.post(
        _baseline_endpoint(ATHLETE_ID), json={"resting_hr": resting_hr}, headers=auth_headers
    )

    assert response.status_code == 422


def test_get_baseline_with_no_existing_row_is_not_found(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.get(_baseline_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 404


def test_get_baseline_returns_most_recently_created_row(
    fake_baseline_repository: FakeBaselineRepository,
    wired_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    now = utc_now().replace(tzinfo=None)
    older = AthletePhysiology(
        physiology_id=uuid.uuid4(),
        athlete_id=ATHLETE_ID,
        session_id=None,
        recorded_date=(now - timedelta(days=2)).date(),
        resting_heart_rate=70,
        created_at=now - timedelta(days=2),
    )
    newer = AthletePhysiology(
        physiology_id=uuid.uuid4(),
        athlete_id=ATHLETE_ID,
        session_id=None,
        recorded_date=now.date(),
        resting_heart_rate=59,
        created_at=now,
    )
    # Inserted out of chronological order deliberately, to prove selection
    # is by `created_at`, not insertion order into the list.
    fake_baseline_repository.rows_by_athlete[ATHLETE_ID] = [newer, older]

    response = wired_client.get(_baseline_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["resting_heart_rate"] == 59
