"""
Sessions module tests: creation and completion.

Uses a fake `SessionRepositoryInterface` and a fake `UserRepositoryInterface`
(via FastAPI's `dependency_overrides`) instead of a real Postgres/Supabase
connection — same convention as `test_onboarding.py`. Requests carry a real
JWT access token (via `create_access_token`), so `get_current_athlete`'s
actual decode-and-lookup logic is exercised end-to-end, not stubbed out.
"""

import uuid
from collections.abc import Iterator
from datetime import datetime

import pytest
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.models.session import Session
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token, create_refresh_token
from app.modules.sessions.dependencies.services import get_session_repository
from app.modules.sessions.repositories.session_repository_interface import SessionRepositoryInterface
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"


def _create_endpoint(athlete_id: str) -> str:
    return f"/api/mobile/athletes/{athlete_id}/sessions"


def _complete_endpoint(athlete_id: str, session_id: uuid.UUID) -> str:
    return f"/api/mobile/athletes/{athlete_id}/sessions/{session_id}/complete"


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by session tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by session tests.")


class FakeSessionRepository(SessionRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed sessions repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number
        self.sessions: dict[uuid.UUID, Session] = {}  # keyed by session_id

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def create(self, athlete_id: str, session_type: str | None) -> Session:
        row = Session(
            session_id=uuid.uuid4(),
            athlete_id=athlete_id,
            session_type=session_type,
            start_time=utc_now().replace(tzinfo=None),
        )
        self.sessions[row.session_id] = row
        return row

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        return self.sessions.get(session_id)

    async def complete(self, row: Session, end_time: datetime) -> Session:
        row.end_time = end_time.replace(tzinfo=None)
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
def fake_session_repository() -> FakeSessionRepository:
    repository = FakeSessionRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_session_repository: FakeSessionRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_session_repository] = lambda: fake_session_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_session_repository, None)


# --- POST /api/mobile/athletes/{athlete_id}/sessions ------------------------------


def test_create_session_success(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_session_repository: FakeSessionRepository,
) -> None:
    response = wired_client.post(
        _create_endpoint(ATHLETE_ID), json={"session_type": "scoring"}, headers=auth_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["athlete_id"] == ATHLETE_ID
    assert body["session_type"] == "scoring"
    assert body["end_time"] is None
    assert uuid.UUID(body["session_id"]) in fake_session_repository.sessions


def test_create_session_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.post(_create_endpoint(ATHLETE_ID), json={"session_type": "scoring"})
    assert response.status_code == 401


def test_create_session_rejects_mismatched_athlete_id(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.post(
        _create_endpoint(OTHER_ATHLETE_ID), json={"session_type": "scoring"}, headers=auth_headers
    )
    assert response.status_code == 403


# --- POST /api/mobile/athletes/{athlete_id}/sessions/{session_id}/complete --------


def test_complete_session_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.post(_complete_endpoint(ATHLETE_ID, uuid.uuid4()))
    assert response.status_code == 401


def test_complete_session_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.post(
        _complete_endpoint(ATHLETE_ID, uuid.uuid4()),
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_complete_session_rejects_refresh_token_used_as_access_token(
    wired_client: TestClient, user_id: uuid.UUID
) -> None:
    refresh_token = create_refresh_token(user_id)
    response = wired_client.post(
        _complete_endpoint(ATHLETE_ID, uuid.uuid4()),
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert response.status_code == 401


def test_complete_session_athlete_not_found(
    wired_client: TestClient, auth_headers: dict[str, str], fake_session_repository: FakeSessionRepository
) -> None:
    fake_session_repository.athletes.pop(PHONE_NUMBER)

    response = wired_client.post(_complete_endpoint(ATHLETE_ID, uuid.uuid4()), headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


def test_complete_session_rejects_mismatched_athlete_id_in_path(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.post(_complete_endpoint(OTHER_ATHLETE_ID, uuid.uuid4()), headers=auth_headers)
    assert response.status_code == 403


def test_complete_session_not_found(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.post(_complete_endpoint(ATHLETE_ID, uuid.uuid4()), headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_complete_session_rejects_another_athletes_session(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_session_repository: FakeSessionRepository,
) -> None:
    other_session = Session(
        session_id=uuid.uuid4(),
        athlete_id=OTHER_ATHLETE_ID,
        session_type="scoring",
        start_time=utc_now().replace(tzinfo=None),
    )
    fake_session_repository.sessions[other_session.session_id] = other_session

    response = wired_client.post(
        _complete_endpoint(ATHLETE_ID, other_session.session_id), headers=auth_headers
    )

    assert response.status_code == 403
    # The other athlete's session must remain untouched.
    assert fake_session_repository.sessions[other_session.session_id].end_time is None


def test_complete_session_success(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_session_repository: FakeSessionRepository,
) -> None:
    session = Session(
        session_id=uuid.uuid4(),
        athlete_id=ATHLETE_ID,
        session_type="scoring",
        start_time=utc_now().replace(tzinfo=None),
    )
    fake_session_repository.sessions[session.session_id] = session

    response = wired_client.post(_complete_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(session.session_id)
    assert body["end_time"] is not None
    assert fake_session_repository.sessions[session.session_id].end_time is not None


def test_complete_session_is_idempotent(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_session_repository: FakeSessionRepository,
) -> None:
    session = Session(
        session_id=uuid.uuid4(),
        athlete_id=ATHLETE_ID,
        session_type="scoring",
        start_time=utc_now().replace(tzinfo=None),
    )
    fake_session_repository.sessions[session.session_id] = session

    first = wired_client.post(_complete_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)
    first_end_time = first.json()["end_time"]

    second = wired_client.post(_complete_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert second.status_code == 200
    assert second.json()["end_time"] == first_end_time  # not overwritten on replay


def test_complete_session_ignores_unknown_score_summary_fields(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_session_repository: FakeSessionRepository,
) -> None:
    session = Session(
        session_id=uuid.uuid4(),
        athlete_id=ATHLETE_ID,
        session_type="scoring",
        start_time=utc_now().replace(tzinfo=None),
    )
    fake_session_repository.sessions[session.session_id] = session

    response = wired_client.post(
        _complete_endpoint(ATHLETE_ID, session.session_id),
        json={
            "duration_minutes": 45,
            "total_shots": 60,
            "total_score": 570.5,
            "performance_rating": 8,
            "notes": "Good session",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["end_time"] is not None
