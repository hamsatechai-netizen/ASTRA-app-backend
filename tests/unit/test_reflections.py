"""
Reflections module tests: authenticated, ownership-validated reflection
persistence.

Uses a fake `ReflectionRepositoryInterface` and a fake
`UserRepositoryInterface` (via FastAPI's `dependency_overrides`) instead of
a real Postgres/Supabase connection — same convention as
`test_scores.py`/`test_heart_rate.py`. Requests carry a real JWT access
token (via `create_access_token`), so `get_current_athlete`'s actual
decode-and-lookup logic is exercised end-to-end, not stubbed out.
"""

import uuid
from collections.abc import Iterator

import pytest
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.models.session import Session
from app.models.session_post_log import SessionPostLog
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token
from app.modules.reflections.dependencies.services import get_reflection_repository
from app.modules.reflections.repositories.session_post_log_repository_interface import (
    ReflectionRepositoryInterface,
)
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"

VALID_BODY = {"mood": 4, "what_worked": "Good focus", "what_didnt": "Rushed final series"}


def _reflection_endpoint(athlete_id: str, session_id: uuid.UUID) -> str:
    return f"/api/mobile/athletes/{athlete_id}/sessions/{session_id}/reflection"


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by reflection tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by reflection tests.")


class FakeReflectionRepository(ReflectionRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed reflections repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number
        self.sessions: dict[uuid.UUID, Session] = {}  # keyed by session_id
        self.reflections: dict[uuid.UUID, SessionPostLog] = {}  # keyed by session_id
        self.upsert_calls = 0

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def get_session_by_id(self, session_id: uuid.UUID) -> Session | None:
        return self.sessions.get(session_id)

    async def upsert_reflection(
        self,
        *,
        session_id: uuid.UUID,
        mood: int | None,
        what_worked: str | None,
        what_didnt: str | None,
    ) -> SessionPostLog:
        self.upsert_calls += 1
        row = SessionPostLog(
            id=uuid.uuid4(),
            session_id=session_id,
            mood=mood,
            what_worked=what_worked,
            what_didnt=what_didnt,
        )
        self.reflections[session_id] = row
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
def fake_reflection_repository() -> FakeReflectionRepository:
    repository = FakeReflectionRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_reflection_repository: FakeReflectionRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_reflection_repository] = lambda: fake_reflection_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_reflection_repository, None)


def _owned_session(athlete_id: str = ATHLETE_ID) -> Session:
    return Session(
        session_id=uuid.uuid4(),
        athlete_id=athlete_id,
        session_type="scoring",
        start_time=utc_now().replace(tzinfo=None),
    )


# --- POST /api/mobile/athletes/{athlete_id}/sessions/{session_id}/reflection ------


def test_save_reflection_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.post(_reflection_endpoint(ATHLETE_ID, uuid.uuid4()), json=VALID_BODY)
    assert response.status_code == 401


def test_save_reflection_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.post(
        _reflection_endpoint(ATHLETE_ID, uuid.uuid4()),
        json=VALID_BODY,
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_save_reflection_athlete_not_found(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_reflection_repository: FakeReflectionRepository,
) -> None:
    fake_reflection_repository.athletes.pop(PHONE_NUMBER)

    response = wired_client.post(
        _reflection_endpoint(ATHLETE_ID, uuid.uuid4()), json=VALID_BODY, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


def test_save_reflection_rejects_mismatched_athlete_id_in_path(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.post(
        _reflection_endpoint(OTHER_ATHLETE_ID, uuid.uuid4()), json=VALID_BODY, headers=auth_headers
    )
    assert response.status_code == 403


def test_save_reflection_session_not_found(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.post(
        _reflection_endpoint(ATHLETE_ID, uuid.uuid4()), json=VALID_BODY, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_save_reflection_rejects_another_athletes_session(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_reflection_repository: FakeReflectionRepository,
) -> None:
    other_session = _owned_session(athlete_id=OTHER_ATHLETE_ID)
    fake_reflection_repository.sessions[other_session.session_id] = other_session

    response = wired_client.post(
        _reflection_endpoint(ATHLETE_ID, other_session.session_id), json=VALID_BODY, headers=auth_headers
    )

    assert response.status_code == 403
    assert other_session.session_id not in fake_reflection_repository.reflections  # nothing written


def test_save_reflection_success_persists_correct_values(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_reflection_repository: FakeReflectionRepository,
) -> None:
    session = _owned_session()
    fake_reflection_repository.sessions[session.session_id] = session

    response = wired_client.post(
        _reflection_endpoint(ATHLETE_ID, session.session_id), json=VALID_BODY, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(session.session_id)
    assert body["mood"] == 4
    assert body["what_worked"] == "Good focus"
    assert body["what_didnt"] == "Rushed final series"

    saved = fake_reflection_repository.reflections[session.session_id]
    assert saved.mood == 4
    assert saved.what_worked == "Good focus"
    assert saved.what_didnt == "Rushed final series"


def test_save_reflection_mood_below_range_rejected(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_reflection_repository: FakeReflectionRepository,
) -> None:
    session = _owned_session()
    fake_reflection_repository.sessions[session.session_id] = session

    response = wired_client.post(
        _reflection_endpoint(ATHLETE_ID, session.session_id),
        json={**VALID_BODY, "mood": 0},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_save_reflection_mood_above_range_rejected(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_reflection_repository: FakeReflectionRepository,
) -> None:
    session = _owned_session()
    fake_reflection_repository.sessions[session.session_id] = session

    response = wired_client.post(
        _reflection_endpoint(ATHLETE_ID, session.session_id),
        json={**VALID_BODY, "mood": 6},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_save_reflection_allows_null_and_empty_fields(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_reflection_repository: FakeReflectionRepository,
) -> None:
    session = _owned_session()
    fake_reflection_repository.sessions[session.session_id] = session

    response = wired_client.post(
        _reflection_endpoint(ATHLETE_ID, session.session_id),
        json={"mood": None, "what_worked": "", "what_didnt": None},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mood"] is None
    assert body["what_worked"] == ""
    assert body["what_didnt"] is None


def test_save_reflection_empty_body_defaults_to_all_null(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_reflection_repository: FakeReflectionRepository,
) -> None:
    session = _owned_session()
    fake_reflection_repository.sessions[session.session_id] = session

    response = wired_client.post(_reflection_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["mood"] is None
    assert body["what_worked"] is None
    assert body["what_didnt"] is None


def test_save_reflection_is_upsert_not_duplicate_on_retry(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_reflection_repository: FakeReflectionRepository,
) -> None:
    session = _owned_session()
    fake_reflection_repository.sessions[session.session_id] = session

    first = wired_client.post(
        _reflection_endpoint(ATHLETE_ID, session.session_id), json=VALID_BODY, headers=auth_headers
    )
    assert first.status_code == 200

    retry_body = {
        "mood": 5,
        "what_worked": "Better focus",
        "what_didnt": "Breathing needs work",
    }
    second = wired_client.post(
        _reflection_endpoint(ATHLETE_ID, session.session_id), json=retry_body, headers=auth_headers
    )

    assert second.status_code == 200
    body = second.json()
    assert body["mood"] == 5
    assert body["what_worked"] == "Better focus"
    assert body["what_didnt"] == "Breathing needs work"

    # Exactly one row for this session — the retry overwrote it, not duplicated it.
    assert len(fake_reflection_repository.reflections) == 1
    assert fake_reflection_repository.upsert_calls == 2
    assert fake_reflection_repository.reflections[session.session_id].mood == 5
