"""
Scores module tests: authenticated, ownership-validated score persistence.

Uses a fake `ScoreRepositoryInterface` and a fake `UserRepositoryInterface`
(via FastAPI's `dependency_overrides`) instead of a real Postgres/Supabase
connection — same convention as `test_sessions.py`/`test_heart_rate.py`.
Requests carry a real JWT access token (via `create_access_token`), so
`get_current_athlete`'s actual decode-and-lookup logic is exercised
end-to-end, not stubbed out.
"""

import uuid
from collections.abc import Iterator
from datetime import date

import pytest
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.models.session import Session
from app.models.shooting_session_log import ShootingSessionLog
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token
from app.modules.scores.dependencies.services import get_score_repository
from app.modules.scores.repositories.shooting_session_log_repository_interface import (
    ScoreRepositoryInterface,
)
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"

VALID_BODY = {"total_shots": 60, "avg_score": 8.75, "best_series_score": 92.5}


def _score_endpoint(athlete_id: str, session_id: uuid.UUID) -> str:
    return f"/api/mobile/athletes/{athlete_id}/sessions/{session_id}/score"


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by score tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by score tests.")


class FakeScoreRepository(ScoreRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed scores repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number
        self.sessions: dict[uuid.UUID, Session] = {}  # keyed by session_id
        self.scores: dict[uuid.UUID, ShootingSessionLog] = {}  # keyed by session_id
        self.upsert_calls = 0

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def get_session_by_id(self, session_id: uuid.UUID) -> Session | None:
        return self.sessions.get(session_id)

    async def upsert_score(
        self,
        *,
        session_id: uuid.UUID,
        athlete_id: str,
        session_date: date,
        session_type: str | None,
        total_shots: int,
        avg_score: float,
        best_series_score: float,
    ) -> ShootingSessionLog:
        self.upsert_calls += 1
        row = ShootingSessionLog(
            session_id=session_id,
            athlete_id=athlete_id,
            session_date=session_date,
            session_type=session_type,
            total_shots=total_shots,
            avg_score=avg_score,
            best_series_score=best_series_score,
        )
        self.scores[session_id] = row
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
def fake_score_repository() -> FakeScoreRepository:
    repository = FakeScoreRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_score_repository: FakeScoreRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_score_repository] = lambda: fake_score_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_score_repository, None)


def _owned_session(athlete_id: str = ATHLETE_ID, session_type: str | None = "scoring") -> Session:
    return Session(
        session_id=uuid.uuid4(),
        athlete_id=athlete_id,
        session_type=session_type,
        start_time=utc_now().replace(tzinfo=None),
    )


# --- POST /api/mobile/athletes/{athlete_id}/sessions/{session_id}/score -----------


def test_save_score_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.post(_score_endpoint(ATHLETE_ID, uuid.uuid4()), json=VALID_BODY)
    assert response.status_code == 401


def test_save_score_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.post(
        _score_endpoint(ATHLETE_ID, uuid.uuid4()),
        json=VALID_BODY,
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_save_score_athlete_not_found(
    wired_client: TestClient, auth_headers: dict[str, str], fake_score_repository: FakeScoreRepository
) -> None:
    fake_score_repository.athletes.pop(PHONE_NUMBER)

    response = wired_client.post(
        _score_endpoint(ATHLETE_ID, uuid.uuid4()), json=VALID_BODY, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


def test_save_score_rejects_mismatched_athlete_id_in_path(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.post(
        _score_endpoint(OTHER_ATHLETE_ID, uuid.uuid4()), json=VALID_BODY, headers=auth_headers
    )
    assert response.status_code == 403


def test_save_score_session_not_found(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.post(
        _score_endpoint(ATHLETE_ID, uuid.uuid4()), json=VALID_BODY, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_save_score_rejects_another_athletes_session(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_score_repository: FakeScoreRepository,
) -> None:
    other_session = _owned_session(athlete_id=OTHER_ATHLETE_ID)
    fake_score_repository.sessions[other_session.session_id] = other_session

    response = wired_client.post(
        _score_endpoint(ATHLETE_ID, other_session.session_id), json=VALID_BODY, headers=auth_headers
    )

    assert response.status_code == 403
    assert other_session.session_id not in fake_score_repository.scores  # nothing written


def test_save_score_success_persists_correct_values(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_score_repository: FakeScoreRepository,
) -> None:
    session = _owned_session(session_type="grouping")
    fake_score_repository.sessions[session.session_id] = session

    response = wired_client.post(
        _score_endpoint(ATHLETE_ID, session.session_id), json=VALID_BODY, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(session.session_id)
    assert body["athlete_id"] == ATHLETE_ID
    assert body["total_shots"] == 60
    assert body["avg_score"] == 8.75
    assert body["best_series_score"] == 92.5

    saved = fake_score_repository.scores[session.session_id]
    assert saved.total_shots == 60
    assert saved.avg_score == 8.75
    assert saved.best_series_score == 92.5
    assert saved.session_type == "grouping"  # copied from the session, not invented
    assert saved.session_date == session.start_time.date()


def test_save_score_is_upsert_not_duplicate_on_retry(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_score_repository: FakeScoreRepository,
) -> None:
    session = _owned_session()
    fake_score_repository.sessions[session.session_id] = session

    first = wired_client.post(
        _score_endpoint(ATHLETE_ID, session.session_id), json=VALID_BODY, headers=auth_headers
    )
    assert first.status_code == 200

    retry_body = {"total_shots": 70, "avg_score": 9.1, "best_series_score": 95.0}
    second = wired_client.post(
        _score_endpoint(ATHLETE_ID, session.session_id), json=retry_body, headers=auth_headers
    )

    assert second.status_code == 200
    body = second.json()
    assert body["total_shots"] == 70
    assert body["avg_score"] == 9.1
    assert body["best_series_score"] == 95.0

    # Exactly one row for this session — the retry overwrote it, not duplicated it.
    assert len(fake_score_repository.scores) == 1
    assert fake_score_repository.upsert_calls == 2
    assert fake_score_repository.scores[session.session_id].total_shots == 70


@pytest.mark.parametrize(
    "invalid_body",
    [
        {**VALID_BODY, "total_shots": -1},
        {**VALID_BODY, "avg_score": -0.1},
        {**VALID_BODY, "best_series_score": -0.1},
        {k: v for k, v in VALID_BODY.items() if k != "total_shots"},
        {k: v for k, v in VALID_BODY.items() if k != "avg_score"},
        {k: v for k, v in VALID_BODY.items() if k != "best_series_score"},
    ],
)
def test_save_score_rejects_invalid_bodies(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_score_repository: FakeScoreRepository,
    invalid_body: dict[str, object],
) -> None:
    session = _owned_session()
    fake_score_repository.sessions[session.session_id] = session

    response = wired_client.post(
        _score_endpoint(ATHLETE_ID, session.session_id), json=invalid_body, headers=auth_headers
    )

    assert response.status_code == 422
