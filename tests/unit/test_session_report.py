"""
Session-report module tests: authenticated, ownership-validated,
read-only aggregation of a session's HR, score, series, and reflection data.

Uses a fake `SessionReportRepositoryInterface` and a fake
`UserRepositoryInterface` (via FastAPI's `dependency_overrides`) instead of
a real Postgres/Supabase connection — same convention as
`test_heart_rate.py`/`test_series.py`. Requests carry a real JWT access
token (via `create_access_token`), so `get_current_athlete`'s actual
decode-and-lookup logic is exercised end-to-end, not stubbed out.

The fake repository's `get_hr_aggregate_for_session` recomputes count/avg/
min/max/first/last from a plain list of (recorded_at, heart_rate) pairs on
every call, mirroring exactly what the real SQL aggregate query computes —
so these tests exercise the same aggregation semantics the production
repository implements, without a real database.
"""

import uuid
from collections.abc import Iterator, Sequence
from datetime import datetime, timedelta

import pytest
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.models.session import Session
from app.models.session_post_log import SessionPostLog
from app.models.session_series import SessionSeries
from app.models.shooting_session_log import ShootingSessionLog
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token
from app.modules.session_report.dependencies.services import get_session_report_repository
from app.modules.session_report.repositories.session_report_repository_interface import (
    HrAggregateRecord,
    SessionReportRepositoryInterface,
)
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"


def _report_endpoint(athlete_id: str, session_id: uuid.UUID) -> str:
    return f"/api/mobile/athletes/{athlete_id}/sessions/{session_id}/report"


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by session-report tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by session-report tests.")


class FakeSessionReportRepository(SessionReportRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed session-report repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number
        self.sessions: dict[uuid.UUID, Session] = {}  # keyed by session_id
        self.hr_samples: dict[uuid.UUID, list[tuple[datetime, int]]] = {}  # keyed by session_id
        self.scores: dict[uuid.UUID, ShootingSessionLog] = {}  # keyed by session_id
        self.series: dict[uuid.UUID, list[SessionSeries]] = {}  # keyed by session_id
        self.reflections: dict[uuid.UUID, SessionPostLog] = {}  # keyed by session_id

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def get_session_by_id(self, session_id: uuid.UUID) -> Session | None:
        return self.sessions.get(session_id)

    async def get_hr_aggregate_for_session(self, session_id: uuid.UUID) -> HrAggregateRecord:
        samples = self.hr_samples.get(session_id, [])
        if not samples:
            return HrAggregateRecord(
                sample_count=0, avg_hr=None, min_hr=None, max_hr=None, first_hr=None, last_hr=None
            )
        ordered = sorted(samples, key=lambda s: s[0])
        heart_rates = [hr for _, hr in samples]
        return HrAggregateRecord(
            sample_count=len(samples),
            avg_hr=round(sum(heart_rates) / len(heart_rates)),
            min_hr=min(heart_rates),
            max_hr=max(heart_rates),
            first_hr=ordered[0][1],
            last_hr=ordered[-1][1],
        )

    async def get_score_for_session(self, session_id: uuid.UUID) -> ShootingSessionLog | None:
        return self.scores.get(session_id)

    async def get_series_for_session(self, session_id: uuid.UUID) -> Sequence[SessionSeries]:
        return sorted(self.series.get(session_id, []), key=lambda s: s.series_number)

    async def get_reflection_for_session(self, session_id: uuid.UUID) -> SessionPostLog | None:
        return self.reflections.get(session_id)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_user_repository(user_id: uuid.UUID) -> FakeUserRepository:
    repository = FakeUserRepository()
    repository.users[user_id] = HamsaTechUser(id=user_id, phone_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def fake_report_repository() -> FakeSessionReportRepository:
    repository = FakeSessionReportRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_report_repository: FakeSessionReportRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_session_report_repository] = lambda: fake_report_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_session_report_repository, None)


def _owned_session(
    athlete_id: str = ATHLETE_ID,
    *,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> Session:
    return Session(
        session_id=uuid.uuid4(),
        athlete_id=athlete_id,
        session_type="scoring",
        start_time=start_time or utc_now().replace(tzinfo=None),
        end_time=end_time,
    )


# --- Authentication / ownership --------------------------------------------------


def test_get_session_report_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.get(_report_endpoint(ATHLETE_ID, uuid.uuid4()))
    assert response.status_code == 401


def test_get_session_report_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.get(
        _report_endpoint(ATHLETE_ID, uuid.uuid4()),
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_get_session_report_athlete_not_found(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_report_repository: FakeSessionReportRepository,
) -> None:
    fake_report_repository.athletes.pop(PHONE_NUMBER)

    response = wired_client.get(_report_endpoint(ATHLETE_ID, uuid.uuid4()), headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


def test_get_session_report_rejects_mismatched_athlete_id_in_path(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.get(_report_endpoint(OTHER_ATHLETE_ID, uuid.uuid4()), headers=auth_headers)
    assert response.status_code == 403


def test_get_session_report_nonexistent_session(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.get(_report_endpoint(ATHLETE_ID, uuid.uuid4()), headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_get_session_report_rejects_another_athletes_session(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_report_repository: FakeSessionReportRepository,
) -> None:
    other_session = _owned_session(athlete_id=OTHER_ATHLETE_ID)
    fake_report_repository.sessions[other_session.session_id] = other_session

    response = wired_client.get(_report_endpoint(ATHLETE_ID, other_session.session_id), headers=auth_headers)

    assert response.status_code == 403


# --- Session status / duration -----------------------------------------------------


def test_get_session_report_in_progress_session_has_null_duration(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_report_repository: FakeSessionReportRepository,
) -> None:
    session = _owned_session()
    fake_report_repository.sessions[session.session_id] = session

    response = wired_client.get(_report_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["session_status"] == "in_progress"
    assert body["session_summary"]["completed_at"] is None
    assert body["session_summary"]["duration_seconds"] is None


def test_get_session_report_completed_session_has_correct_duration(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_report_repository: FakeSessionReportRepository,
) -> None:
    start = datetime(2026, 8, 20, 9, 0, 0)
    end = datetime(2026, 8, 20, 9, 42, 30)
    session = _owned_session(start_time=start, end_time=end)
    fake_report_repository.sessions[session.session_id] = session

    response = wired_client.get(_report_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["session_status"] == "completed"
    assert body["session_summary"]["duration_seconds"] == 42 * 60 + 30


# --- Missing-data cases: each category degrades independently ----------------------


def test_get_session_report_with_no_heart_rate_data(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_report_repository: FakeSessionReportRepository,
) -> None:
    session = _owned_session()
    fake_report_repository.sessions[session.session_id] = session
    fake_report_repository.scores[session.session_id] = ShootingSessionLog(
        session_id=session.session_id,
        athlete_id=ATHLETE_ID,
        session_date=session.start_time.date(),
        total_shots=60,
        avg_score=8.5,
        best_series_score=90.0,
    )

    response = wired_client.get(_report_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    hr = response.json()["heart_rate"]
    assert hr == {
        "sample_count": 0,
        "average_heart_rate": None,
        "minimum_heart_rate": None,
        "maximum_heart_rate": None,
        "first_heart_rate": None,
        "last_heart_rate": None,
    }


def test_get_session_report_scores_null_when_no_score_and_no_series(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_report_repository: FakeSessionReportRepository,
) -> None:
    session = _owned_session()
    fake_report_repository.sessions[session.session_id] = session

    response = wired_client.get(_report_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["scores"] is None
    assert body["series"] == []


def test_get_session_report_scores_populated_from_series_only(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_report_repository: FakeSessionReportRepository,
) -> None:
    session = _owned_session()
    fake_report_repository.sessions[session.session_id] = session
    fake_report_repository.series[session.session_id] = [
        SessionSeries(
            id=uuid.uuid4(), session_id=session.session_id, series_number=1, total_score=80.0, shots_fired=10
        ),
        SessionSeries(
            id=uuid.uuid4(), session_id=session.session_id, series_number=2, total_score=90.0, shots_fired=10
        ),
    ]

    response = wired_client.get(_report_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    scores = response.json()["scores"]
    assert scores["total_shots"] is None
    assert scores["avg_score"] is None
    assert scores["best_series_score"] is None
    assert scores["total_score"] == 170.0
    assert scores["average_score"] == 85.0
    assert scores["minimum_score"] == 80.0
    assert scores["maximum_score"] == 90.0


def test_get_session_report_scores_populated_from_score_summary_only(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_report_repository: FakeSessionReportRepository,
) -> None:
    session = _owned_session()
    fake_report_repository.sessions[session.session_id] = session
    fake_report_repository.scores[session.session_id] = ShootingSessionLog(
        session_id=session.session_id,
        athlete_id=ATHLETE_ID,
        session_date=session.start_time.date(),
        total_shots=60,
        avg_score=8.5,
        best_series_score=92.0,
    )

    response = wired_client.get(_report_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    scores = body["scores"]
    assert scores["total_shots"] == 60
    assert scores["avg_score"] == 8.5
    assert scores["best_series_score"] == 92.0
    assert scores["total_score"] is None
    assert scores["average_score"] is None
    assert scores["minimum_score"] is None
    assert scores["maximum_score"] is None
    assert body["series"] == []


def test_get_session_report_with_no_reflection(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_report_repository: FakeSessionReportRepository,
) -> None:
    session = _owned_session()
    fake_report_repository.sessions[session.session_id] = session

    response = wired_client.get(_report_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["reflection"] is None


# --- Aggregation correctness --------------------------------------------------------


def test_get_session_report_hr_aggregate_correctness(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_report_repository: FakeSessionReportRepository,
) -> None:
    session = _owned_session()
    fake_report_repository.sessions[session.session_id] = session
    base = datetime(2026, 8, 20, 10, 0, 0)
    heart_rates = [80, 84, 88, 92, 76]
    fake_report_repository.hr_samples[session.session_id] = [
        (base + timedelta(seconds=i), hr) for i, hr in enumerate(heart_rates)
    ]

    response = wired_client.get(_report_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    hr = response.json()["heart_rate"]
    assert hr["sample_count"] == 5
    assert hr["average_heart_rate"] == round(sum(heart_rates) / len(heart_rates))
    assert hr["minimum_heart_rate"] == 76
    assert hr["maximum_heart_rate"] == 92
    assert hr["first_heart_rate"] == 80  # earliest recorded_at
    assert hr["last_heart_rate"] == 76  # latest recorded_at


# --- Full, complete-data report ------------------------------------------------------


def test_get_session_report_full_data(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_report_repository: FakeSessionReportRepository,
) -> None:
    start = datetime(2026, 8, 20, 9, 0, 0)
    end = datetime(2026, 8, 20, 9, 30, 0)
    session = _owned_session(start_time=start, end_time=end)
    fake_report_repository.sessions[session.session_id] = session

    base = datetime(2026, 8, 20, 9, 0, 0)
    fake_report_repository.hr_samples[session.session_id] = [
        (base + timedelta(seconds=i), hr) for i, hr in enumerate([70, 75, 80])
    ]
    fake_report_repository.scores[session.session_id] = ShootingSessionLog(
        session_id=session.session_id,
        athlete_id=ATHLETE_ID,
        session_date=session.start_time.date(),
        total_shots=20,
        avg_score=9.0,
        best_series_score=95.0,
    )
    fake_report_repository.series[session.session_id] = [
        SessionSeries(
            id=uuid.uuid4(), session_id=session.session_id, series_number=1, total_score=95.0, shots_fired=10
        ),
        SessionSeries(
            id=uuid.uuid4(), session_id=session.session_id, series_number=2, total_score=88.0, shots_fired=10
        ),
    ]
    fake_report_repository.reflections[session.session_id] = SessionPostLog(
        id=uuid.uuid4(),
        session_id=session.session_id,
        mood=4,
        what_worked="Follow-through was consistent",
        what_didnt="Rushed the last series",
    )

    response = wired_client.get(_report_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()

    assert body["session_id"] == str(session.session_id)
    assert body["athlete_id"] == ATHLETE_ID
    assert body["session_status"] == "completed"

    assert body["session_summary"]["session_type"] == "scoring"
    assert body["session_summary"]["duration_seconds"] == 30 * 60

    assert body["heart_rate"]["sample_count"] == 3
    assert body["heart_rate"]["average_heart_rate"] == 75
    assert body["heart_rate"]["minimum_heart_rate"] == 70
    assert body["heart_rate"]["maximum_heart_rate"] == 80

    assert body["scores"]["total_shots"] == 20
    assert body["scores"]["avg_score"] == 9.0
    assert body["scores"]["best_series_score"] == 95.0
    assert body["scores"]["total_score"] == 183.0
    assert body["scores"]["average_score"] == 91.5
    assert body["scores"]["minimum_score"] == 88.0
    assert body["scores"]["maximum_score"] == 95.0

    assert len(body["series"]) == 2
    assert body["series"][0] == {"series_number": 1, "total_score": 95.0, "shots_fired": 10}
    assert body["series"][1] == {"series_number": 2, "total_score": 88.0, "shots_fired": 10}

    assert body["reflection"] == {
        "mood": 4,
        "what_worked": "Follow-through was consistent",
        "what_didnt": "Rushed the last series",
    }

    # Response schema validation — every top-level key the schema declares is present.
    assert set(body.keys()) == {
        "session_id",
        "athlete_id",
        "session_status",
        "session_summary",
        "heart_rate",
        "scores",
        "series",
        "reflection",
    }
