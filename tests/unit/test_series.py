"""
Series module tests: authenticated, ownership-validated per-series
persistence.

Uses a fake `SeriesRepositoryInterface` and a fake `UserRepositoryInterface`
(via FastAPI's `dependency_overrides`) instead of a real Postgres/Supabase
connection — same convention as `test_scores.py`/`test_reflections.py`.
Requests carry a real JWT access token (via `create_access_token`), so
`get_current_athlete`'s actual decode-and-lookup logic is exercised
end-to-end, not stubbed out.
"""

import uuid
from collections.abc import Iterator

import pytest
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.models.session import Session
from app.models.session_series import SessionSeries
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token
from app.modules.series.dependencies.services import get_series_repository
from app.modules.series.repositories.session_series_repository_interface import (
    SeriesRepositoryInterface,
)
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"

VALID_BODY = {"series_number": 1, "total_score": 92.5, "shots_fired": 10}


def _series_endpoint(athlete_id: str, session_id: uuid.UUID) -> str:
    return f"/api/mobile/athletes/{athlete_id}/sessions/{session_id}/series"


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by series tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by series tests.")


class FakeSeriesRepository(SeriesRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed series repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number
        self.sessions: dict[uuid.UUID, Session] = {}  # keyed by session_id
        self.series: dict[tuple[uuid.UUID, int], SessionSeries] = {}  # keyed by (session_id, series_number)
        self.upsert_calls = 0

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def get_session_by_id(self, session_id: uuid.UUID) -> Session | None:
        return self.sessions.get(session_id)

    async def upsert_series(
        self,
        *,
        session_id: uuid.UUID,
        series_number: int,
        total_score: float,
        shots_fired: int,
    ) -> SessionSeries:
        self.upsert_calls += 1
        row = SessionSeries(
            id=uuid.uuid4(),
            session_id=session_id,
            series_number=series_number,
            total_score=total_score,
            shots_fired=shots_fired,
        )
        self.series[(session_id, series_number)] = row
        return row


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_user_repository(user_id: uuid.UUID) -> FakeUserRepository:
    repository = FakeUserRepository()
    repository.users[user_id] = HamsaTechUser(id=user_id, phone_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def fake_series_repository() -> FakeSeriesRepository:
    repository = FakeSeriesRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_series_repository: FakeSeriesRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_series_repository] = lambda: fake_series_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_series_repository, None)


def _owned_session(athlete_id: str = ATHLETE_ID) -> Session:
    return Session(
        session_id=uuid.uuid4(),
        athlete_id=athlete_id,
        session_type="scoring",
        start_time=utc_now().replace(tzinfo=None),
    )


# --- POST /api/mobile/athletes/{athlete_id}/sessions/{session_id}/series ----------


def test_save_series_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.post(_series_endpoint(ATHLETE_ID, uuid.uuid4()), json=VALID_BODY)
    assert response.status_code == 401


def test_save_series_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.post(
        _series_endpoint(ATHLETE_ID, uuid.uuid4()),
        json=VALID_BODY,
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_save_series_athlete_not_found(
    wired_client: TestClient, auth_headers: dict[str, str], fake_series_repository: FakeSeriesRepository
) -> None:
    fake_series_repository.athletes.pop(PHONE_NUMBER)

    response = wired_client.post(
        _series_endpoint(ATHLETE_ID, uuid.uuid4()), json=VALID_BODY, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


def test_save_series_rejects_mismatched_athlete_id_in_path(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.post(
        _series_endpoint(OTHER_ATHLETE_ID, uuid.uuid4()), json=VALID_BODY, headers=auth_headers
    )
    assert response.status_code == 403


def test_save_series_session_not_found(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.post(
        _series_endpoint(ATHLETE_ID, uuid.uuid4()), json=VALID_BODY, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_save_series_rejects_another_athletes_session(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_series_repository: FakeSeriesRepository,
) -> None:
    other_session = _owned_session(athlete_id=OTHER_ATHLETE_ID)
    fake_series_repository.sessions[other_session.session_id] = other_session

    response = wired_client.post(
        _series_endpoint(ATHLETE_ID, other_session.session_id), json=VALID_BODY, headers=auth_headers
    )

    assert response.status_code == 403
    assert (other_session.session_id, 1) not in fake_series_repository.series  # nothing written


def test_save_series_success_persists_correct_values(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_series_repository: FakeSeriesRepository,
) -> None:
    session = _owned_session()
    fake_series_repository.sessions[session.session_id] = session

    response = wired_client.post(
        _series_endpoint(ATHLETE_ID, session.session_id), json=VALID_BODY, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(session.session_id)
    assert body["series_number"] == 1
    assert body["total_score"] == 92.5
    assert body["shots_fired"] == 10

    saved = fake_series_repository.series[(session.session_id, 1)]
    assert saved.total_score == 92.5
    assert saved.shots_fired == 10


def test_save_series_multiple_series_coexist_for_same_session(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_series_repository: FakeSeriesRepository,
) -> None:
    session = _owned_session()
    fake_series_repository.sessions[session.session_id] = session

    for series_number in (1, 2, 3):
        response = wired_client.post(
            _series_endpoint(ATHLETE_ID, session.session_id),
            json={"series_number": series_number, "total_score": 80.0 + series_number, "shots_fired": 10},
            headers=auth_headers,
        )
        assert response.status_code == 200

    # Three distinct rows for the same session — one per series_number.
    assert len(fake_series_repository.series) == 3
    for series_number in (1, 2, 3):
        row = fake_series_repository.series[(session.session_id, series_number)]
        assert row.total_score == 80.0 + series_number


def test_save_series_is_upsert_not_duplicate_on_retry(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_series_repository: FakeSeriesRepository,
) -> None:
    session = _owned_session()
    fake_series_repository.sessions[session.session_id] = session

    first = wired_client.post(
        _series_endpoint(ATHLETE_ID, session.session_id), json=VALID_BODY, headers=auth_headers
    )
    assert first.status_code == 200

    retry_body = {"series_number": 1, "total_score": 95.0, "shots_fired": 10}
    second = wired_client.post(
        _series_endpoint(ATHLETE_ID, session.session_id), json=retry_body, headers=auth_headers
    )

    assert second.status_code == 200
    body = second.json()
    assert body["total_score"] == 95.0

    # Exactly one row for this (session_id, series_number) — retry overwrote it.
    assert len(fake_series_repository.series) == 1
    assert fake_series_repository.upsert_calls == 2
    assert fake_series_repository.series[(session.session_id, 1)].total_score == 95.0


@pytest.mark.parametrize(
    "invalid_body",
    [
        {**VALID_BODY, "series_number": 0},
        {**VALID_BODY, "total_score": -1},
        {**VALID_BODY, "shots_fired": -1},
        {k: v for k, v in VALID_BODY.items() if k != "series_number"},
        {k: v for k, v in VALID_BODY.items() if k != "total_score"},
        {k: v for k, v in VALID_BODY.items() if k != "shots_fired"},
    ],
)
def test_save_series_rejects_invalid_bodies(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_series_repository: FakeSeriesRepository,
    invalid_body: dict[str, object],
) -> None:
    session = _owned_session()
    fake_series_repository.sessions[session.session_id] = session

    response = wired_client.post(
        _series_endpoint(ATHLETE_ID, session.session_id), json=invalid_body, headers=auth_headers
    )

    assert response.status_code == 422
