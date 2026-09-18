"""
Session-list module tests: paginated session history.

Uses a fake `SessionListRepositoryInterface` and a fake
`UserRepositoryInterface` (via FastAPI's `dependency_overrides`) instead of
a real Postgres/Supabase connection — same convention as
`test_sessions.py`/`test_dashboard.py`. Requests carry a real JWT access
token (via `create_access_token`), so `get_current_athlete`'s actual
decode-and-lookup logic is exercised end-to-end, not stubbed out.
"""

import uuid
from collections.abc import Iterator, Sequence
from datetime import datetime, timedelta

import pytest
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.models.session import Session
from app.models.shooting_session_log import ShootingSessionLog
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token, create_refresh_token
from app.modules.sessions.dependencies.services import get_session_list_repository
from app.modules.sessions.repositories.session_list_repository_interface import (
    SessionHistoryRecord,
    SessionListRepositoryInterface,
)
from fastapi.testclient import TestClient

PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"


def _sessions_endpoint(athlete_id: str, query: str = "") -> str:
    return f"/api/mobile/athletes/{athlete_id}/sessions{query}"


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by session-history tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by session-history tests.")


class FakeSessionListRepository(SessionListRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed session-list repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number
        self.records: dict[str, list[SessionHistoryRecord]] = {}  # keyed by athlete_id

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def count_completed_sessions(self, athlete_id: str) -> int:
        return len(self.records.get(athlete_id, []))

    async def list_completed_sessions(
        self, athlete_id: str, limit: int, offset: int
    ) -> Sequence[SessionHistoryRecord]:
        all_records = sorted(
            self.records.get(athlete_id, []), key=lambda r: r.session.start_time, reverse=True
        )
        return all_records[offset : offset + limit]


def _make_record(
    *,
    athlete_id: str,
    start_time: datetime,
    end_time: datetime | None,
    avg_score: float | None = None,
    best_series_score: float | None = None,
    total_shots: int | None = None,
    series_count: int = 0,
) -> SessionHistoryRecord:
    session_id = uuid.uuid4()
    session = Session(
        session_id=session_id,
        athlete_id=athlete_id,
        session_type="scoring",
        start_time=start_time,
        end_time=end_time,
    )
    score = None
    if avg_score is not None or best_series_score is not None or total_shots is not None:
        score = ShootingSessionLog(
            session_id=session_id,
            athlete_id=athlete_id,
            session_date=start_time.date(),
            avg_score=avg_score,
            best_series_score=best_series_score,
            total_shots=total_shots,
        )
    return SessionHistoryRecord(session=session, score=score, series_count=series_count)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_user_repository(user_id: uuid.UUID) -> FakeUserRepository:
    repository = FakeUserRepository()
    repository.users[user_id] = HamsaTechUser(id=user_id, phone_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def fake_session_list_repository() -> FakeSessionListRepository:
    repository = FakeSessionListRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_session_list_repository: FakeSessionListRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_session_list_repository] = lambda: fake_session_list_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_session_list_repository, None)


# --- GET /api/mobile/athletes/{athlete_id}/sessions ---------------------------------


def test_list_sessions_success(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_session_list_repository: FakeSessionListRepository,
) -> None:
    now = datetime(2026, 6, 1, 10, 0, 0)
    fake_session_list_repository.records[ATHLETE_ID] = [
        _make_record(
            athlete_id=ATHLETE_ID,
            start_time=now,
            end_time=now + timedelta(minutes=45),
            avg_score=8.4,
            best_series_score=95.0,
            total_shots=60,
            series_count=6,
        )
    ]

    response = wired_client.get(_sessions_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {"total": 1, "page": 1, "page_size": 20, "total_pages": 1}
    item = body["data"][0]
    assert item["session_type"] == "scoring"
    assert item["duration_seconds"] == 45 * 60
    assert item["avg_score"] == 8.4
    assert item["best_series_score"] == 95.0
    assert item["total_shots"] == 60
    assert item["series_count"] == 6


def test_list_sessions_empty_history_returns_empty_list(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.get(_sessions_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0
    assert body["meta"]["total_pages"] == 0


def test_list_sessions_never_fabricates_score_when_absent(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_session_list_repository: FakeSessionListRepository,
) -> None:
    now = datetime(2026, 6, 1, 10, 0, 0)
    fake_session_list_repository.records[ATHLETE_ID] = [
        _make_record(athlete_id=ATHLETE_ID, start_time=now, end_time=now + timedelta(minutes=20))
    ]

    response = wired_client.get(_sessions_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    item = response.json()["data"][0]
    assert item["avg_score"] is None
    assert item["best_series_score"] is None
    assert item["total_shots"] is None
    assert item["series_count"] == 0


def test_list_sessions_newest_first(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_session_list_repository: FakeSessionListRepository,
) -> None:
    base = datetime(2026, 6, 1, 10, 0, 0)
    fake_session_list_repository.records[ATHLETE_ID] = [
        _make_record(athlete_id=ATHLETE_ID, start_time=base, end_time=base + timedelta(minutes=10)),
        _make_record(
            athlete_id=ATHLETE_ID,
            start_time=base + timedelta(days=2),
            end_time=base + timedelta(days=2, minutes=10),
        ),
        _make_record(
            athlete_id=ATHLETE_ID,
            start_time=base + timedelta(days=1),
            end_time=base + timedelta(days=1, minutes=10),
        ),
    ]

    response = wired_client.get(_sessions_endpoint(ATHLETE_ID), headers=auth_headers)

    dates = [item["start_time"] for item in response.json()["data"]]
    assert dates == sorted(dates, reverse=True)


def test_list_sessions_only_returns_own_athletes_sessions(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_session_list_repository: FakeSessionListRepository,
) -> None:
    now = datetime(2026, 6, 1, 10, 0, 0)
    fake_session_list_repository.records[ATHLETE_ID] = [
        _make_record(athlete_id=ATHLETE_ID, start_time=now, end_time=now + timedelta(minutes=10))
    ]
    fake_session_list_repository.records[OTHER_ATHLETE_ID] = [
        _make_record(athlete_id=OTHER_ATHLETE_ID, start_time=now, end_time=now + timedelta(minutes=10))
    ]

    response = wired_client.get(_sessions_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_list_sessions_pagination(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_session_list_repository: FakeSessionListRepository,
) -> None:
    base = datetime(2026, 6, 1, 10, 0, 0)
    fake_session_list_repository.records[ATHLETE_ID] = [
        _make_record(
            athlete_id=ATHLETE_ID,
            start_time=base + timedelta(days=i),
            end_time=base + timedelta(days=i, minutes=10),
        )
        for i in range(5)
    ]

    page_1 = wired_client.get(
        _sessions_endpoint(ATHLETE_ID, "?page=1&page_size=2"), headers=auth_headers
    ).json()
    page_2 = wired_client.get(
        _sessions_endpoint(ATHLETE_ID, "?page=2&page_size=2"), headers=auth_headers
    ).json()

    assert len(page_1["data"]) == 2
    assert len(page_2["data"]) == 2
    assert page_1["meta"] == {"total": 5, "page": 1, "page_size": 2, "total_pages": 3}
    assert page_2["meta"]["page"] == 2
    # No overlap between pages.
    page_1_ids = {item["session_id"] for item in page_1["data"]}
    page_2_ids = {item["session_id"] for item in page_2["data"]}
    assert page_1_ids.isdisjoint(page_2_ids)


def test_list_sessions_page_size_is_bounded(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.get(_sessions_endpoint(ATHLETE_ID, "?page_size=1000"), headers=auth_headers)
    assert response.status_code == 422  # exceeds MAX_PAGE_SIZE


def test_list_sessions_schema_has_no_sensitive_fields(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_session_list_repository: FakeSessionListRepository,
) -> None:
    now = datetime(2026, 6, 1, 10, 0, 0)
    fake_session_list_repository.records[ATHLETE_ID] = [
        _make_record(athlete_id=ATHLETE_ID, start_time=now, end_time=now + timedelta(minutes=10))
    ]

    response = wired_client.get(_sessions_endpoint(ATHLETE_ID), headers=auth_headers)

    item = response.json()["data"][0]
    assert set(item.keys()) == {
        "session_id",
        "session_type",
        "start_time",
        "end_time",
        "duration_seconds",
        "avg_score",
        "best_series_score",
        "total_shots",
        "series_count",
    }
    for forbidden_key in (
        "password",
        "otp",
        "token",
        "jwt",
        "contact_number",
        "athlete_id",
        "readiness",
        "recovery",
        "stress",
        "steady",
        "streak",
        "ai_insights",
    ):
        assert forbidden_key not in item


def test_list_sessions_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.get(_sessions_endpoint(ATHLETE_ID))
    assert response.status_code == 401


def test_list_sessions_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.get(
        _sessions_endpoint(ATHLETE_ID), headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_list_sessions_rejects_refresh_token_used_as_access_token(
    wired_client: TestClient, user_id: uuid.UUID
) -> None:
    refresh_token = create_refresh_token(user_id)
    response = wired_client.get(
        _sessions_endpoint(ATHLETE_ID), headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert response.status_code == 401


def test_list_sessions_rejects_mismatched_athlete_id(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.get(_sessions_endpoint(OTHER_ATHLETE_ID), headers=auth_headers)
    assert response.status_code == 403


def test_list_sessions_athlete_not_found(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_session_list_repository: FakeSessionListRepository,
) -> None:
    fake_session_list_repository.athletes.pop(PHONE_NUMBER)

    response = wired_client.get(_sessions_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"
