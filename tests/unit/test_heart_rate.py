"""
Heart-rate module tests: sample ingestion (with session validation) and
session HR read-back.

Uses a fake `HrStreamRepositoryInterface` and a fake `UserRepositoryInterface`
(via FastAPI's `dependency_overrides`) instead of a real Postgres/Supabase
connection — same convention as `test_sessions.py`/`test_onboarding.py`.
Requests carry a real JWT access token (via `create_access_token`), so
`get_current_athlete`'s actual decode-and-lookup logic is exercised
end-to-end, not stubbed out.
"""

import uuid
from collections.abc import Iterator, Sequence
from datetime import datetime, timedelta

import pytest
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.models.session import Session
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token
from app.modules.heart_rate.dependencies.services import get_hr_stream_repository
from app.modules.heart_rate.repositories.hr_stream_repository_interface import (
    HrSampleRecord,
    HrStreamRepositoryInterface,
)
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

SAMPLES_ENDPOINT = "/api/v2/heart-rate/samples"
PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"


def _hr_endpoint(athlete_id: str, session_id: uuid.UUID) -> str:
    return f"/api/mobile/athletes/{athlete_id}/sessions/{session_id}/heart-rate"


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by heart-rate tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by heart-rate tests.")


class FakeHrStreamRepository(HrStreamRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed HR-stream repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number
        self.sessions: dict[uuid.UUID, Session] = {}  # keyed by session_id
        self.samples: dict[uuid.UUID, list[HrSampleRecord]] = {}  # keyed by session_id
        self.inserted: list[HrSampleRecord] = []

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def create_many(self, athlete_id: str, samples: Sequence[HrSampleRecord]) -> int:
        self.inserted.extend(samples)
        for sample in samples:
            self.samples.setdefault(sample.session_id, []).append(sample)
        return len(samples)

    async def get_session_by_id(self, session_id: uuid.UUID) -> Session | None:
        return self.sessions.get(session_id)

    async def get_samples_for_session(self, session_id: uuid.UUID) -> Sequence[HrSampleRecord]:
        return sorted(self.samples.get(session_id, []), key=lambda s: s.recorded_at)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_user_repository(user_id: uuid.UUID) -> FakeUserRepository:
    repository = FakeUserRepository()
    repository.users[user_id] = HamsaTechUser(id=user_id, phone_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def fake_hr_repository() -> FakeHrStreamRepository:
    repository = FakeHrStreamRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_hr_repository: FakeHrStreamRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_hr_stream_repository] = lambda: fake_hr_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_hr_stream_repository, None)


def _owned_session(athlete_id: str = ATHLETE_ID) -> Session:
    return Session(
        session_id=uuid.uuid4(),
        athlete_id=athlete_id,
        session_type="scoring",
        start_time=utc_now().replace(tzinfo=None),
    )


def _sample_payload(session_id: uuid.UUID, *, heart_rate: int = 90) -> dict[str, object]:
    return {
        "samples": [
            {
                "sessionId": str(session_id),
                "recordedAt": utc_now().replace(tzinfo=None).isoformat(),
                "heartRate": heart_rate,
                "rrInterval": 650,
            }
        ]
    }


# --- POST /api/v2/heart-rate/samples — ingestion + session validation -------------


def test_record_samples_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.post(SAMPLES_ENDPOINT, json=_sample_payload(uuid.uuid4()))
    assert response.status_code == 401


def test_record_samples_athlete_not_found(
    wired_client: TestClient, auth_headers: dict[str, str], fake_hr_repository: FakeHrStreamRepository
) -> None:
    fake_hr_repository.athletes.pop(PHONE_NUMBER)

    response = wired_client.post(SAMPLES_ENDPOINT, json=_sample_payload(uuid.uuid4()), headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


def test_record_samples_rejects_nonexistent_session(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.post(SAMPLES_ENDPOINT, json=_sample_payload(uuid.uuid4()), headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_record_samples_rejects_another_athletes_session(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_hr_repository: FakeHrStreamRepository,
) -> None:
    other_session = _owned_session(athlete_id=OTHER_ATHLETE_ID)
    fake_hr_repository.sessions[other_session.session_id] = other_session

    response = wired_client.post(
        SAMPLES_ENDPOINT, json=_sample_payload(other_session.session_id), headers=auth_headers
    )

    assert response.status_code == 403
    assert fake_hr_repository.inserted == []  # nothing written for a rejected batch


def test_record_samples_success(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_hr_repository: FakeHrStreamRepository,
) -> None:
    session = _owned_session()
    fake_hr_repository.sessions[session.session_id] = session

    response = wired_client.post(
        SAMPLES_ENDPOINT, json=_sample_payload(session.session_id, heart_rate=97), headers=auth_headers
    )

    assert response.status_code == 201
    assert response.json()["accepted"] == 1
    assert len(fake_hr_repository.samples[session.session_id]) == 1
    assert fake_hr_repository.samples[session.session_id][0].heart_rate == 97


# --- GET .../sessions/{session_id}/heart-rate --------------------------------------


def test_get_session_hr_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.get(_hr_endpoint(ATHLETE_ID, uuid.uuid4()))
    assert response.status_code == 401


def test_get_session_hr_rejects_mismatched_athlete_id_in_path(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.get(_hr_endpoint(OTHER_ATHLETE_ID, uuid.uuid4()), headers=auth_headers)
    assert response.status_code == 403


def test_get_session_hr_nonexistent_session(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.get(_hr_endpoint(ATHLETE_ID, uuid.uuid4()), headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_get_session_hr_rejects_another_athletes_session(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_hr_repository: FakeHrStreamRepository,
) -> None:
    other_session = _owned_session(athlete_id=OTHER_ATHLETE_ID)
    fake_hr_repository.sessions[other_session.session_id] = other_session

    response = wired_client.get(_hr_endpoint(ATHLETE_ID, other_session.session_id), headers=auth_headers)

    assert response.status_code == 403


def test_get_session_hr_owned_session_with_no_hr(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_hr_repository: FakeHrStreamRepository,
) -> None:
    session = _owned_session()
    fake_hr_repository.sessions[session.session_id] = session

    response = wired_client.get(_hr_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(session.session_id)
    assert body["sample_count"] == 0
    assert body["avg_hr"] is None
    assert body["min_hr"] is None
    assert body["max_hr"] is None
    assert body["points"] == []


def test_get_session_hr_correct_aggregates(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_hr_repository: FakeHrStreamRepository,
) -> None:
    session = _owned_session()
    fake_hr_repository.sessions[session.session_id] = session
    base = datetime(2026, 8, 13, 10, 0, 0)
    heart_rates = [80, 84, 88, 92, 76]
    fake_hr_repository.samples[session.session_id] = [
        HrSampleRecord(
            session_id=session.session_id,
            recorded_at=base + timedelta(seconds=i),
            heart_rate=hr,
            rr_interval=None,
        )
        for i, hr in enumerate(heart_rates)
    ]

    response = wired_client.get(_hr_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["sample_count"] == 5
    assert body["avg_hr"] == round(sum(heart_rates) / len(heart_rates))
    assert body["min_hr"] == 76
    assert body["max_hr"] == 92


def test_get_session_hr_points_are_chronologically_ordered(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_hr_repository: FakeHrStreamRepository,
) -> None:
    session = _owned_session()
    fake_hr_repository.sessions[session.session_id] = session
    base = datetime(2026, 8, 13, 10, 0, 0)
    # Insert out of order — repository is responsible for sorting.
    fake_hr_repository.samples[session.session_id] = [
        HrSampleRecord(session.session_id, base + timedelta(seconds=2), 90, None),
        HrSampleRecord(session.session_id, base, 80, None),
        HrSampleRecord(session.session_id, base + timedelta(seconds=1), 85, None),
    ]

    response = wired_client.get(_hr_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    points = response.json()["points"]
    recorded = [p["recorded_at"] for p in points]
    assert recorded == sorted(recorded)
    assert [p["heart_rate"] for p in points] == [80, 85, 90]


def test_get_session_hr_downsamples_large_sample_sets(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_hr_repository: FakeHrStreamRepository,
) -> None:
    session = _owned_session()
    fake_hr_repository.sessions[session.session_id] = session
    base = datetime(2026, 8, 13, 10, 0, 0)
    total = 500
    fake_hr_repository.samples[session.session_id] = [
        HrSampleRecord(session.session_id, base + timedelta(seconds=i), 70 + (i % 20), None)
        for i in range(total)
    ]

    response = wired_client.get(_hr_endpoint(ATHLETE_ID, session.session_id), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["sample_count"] == total  # aggregates computed over the FULL set
    assert len(body["points"]) <= 120
    points = body["points"]
    recorded = [p["recorded_at"] for p in points]
    assert recorded == sorted(recorded)  # still chronological
    # First and last real samples must be preserved (full time range kept).
    assert points[0]["recorded_at"] == (base + timedelta(seconds=0)).isoformat()
    assert points[-1]["recorded_at"] == (base + timedelta(seconds=total - 1)).isoformat()
