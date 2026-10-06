"""
ECG/ACC sample-ingestion tests (`POST /api/v2/ecg/samples`, `POST /api/v2/acc/samples`).

Same conventions as `test_heart_rate.py`: a fake `SensorStreamRepositoryInterface`
and a fake `UserRepositoryInterface` (via FastAPI's `dependency_overrides`)
instead of a real Postgres/Supabase connection, and real JWT access tokens
(via `create_access_token`) so `get_current_athlete`'s actual
decode-and-lookup logic is exercised end-to-end.

The bulk-insert and rollback tests go one layer deeper: they keep the real
`get_db` dependency and the real `SensorStreamRepository`, and replace only
the `AsyncSession` factory with an in-memory fake, so the actual SQL
statement shape and the commit/rollback transaction boundary are verified.

Every behavioral test is parametrized over both streams.
"""

import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from app.main import app as fastapi_app
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.models.sensor_ingestion_batch import SensorIngestionBatch
from app.models.session import Session
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token
from app.modules.sensor_streams.dependencies.body import MAX_BODY_BYTES
from app.modules.sensor_streams.dependencies.services import get_sensor_stream_repository
from app.modules.sensor_streams.repositories.sensor_stream_repository_interface import (
    AccSampleRecord,
    EcgSampleRecord,
    SensorStreamRepositoryInterface,
)
from app.modules.sensor_streams.routers.common import PER_CALLER_LIMIT
from app.modules.sensor_streams.schemas import MAX_BATCH_SIZE
from app.security.rate_limiter import authenticated_caller_key, limiter
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import Insert, Select
from starlette.requests import Request

PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"
IST = timezone(timedelta(hours=5, minutes=30))


# --- Stream specs: one per endpoint, so every test runs against both ---------


@dataclass(frozen=True)
class StreamSpec:
    name: str
    endpoint: str
    table: str
    make_sample: Callable[[int], dict[str, object]]
    value_keys: tuple[str, ...]
    out_of_range_value: int


def _recorded_at(offset_ms: int = 0) -> str:
    return (utc_now() + timedelta(milliseconds=offset_ms)).isoformat()


ECG = StreamSpec(
    name="ecg",
    endpoint="/api/v2/ecg/samples",
    table="ecg_stream",
    make_sample=lambda i: {"recordedAt": _recorded_at(i * 8), "ecgValue": -120 + i},
    value_keys=("ecgValue",),
    out_of_range_value=100_001,
)
ACC = StreamSpec(
    name="acc",
    endpoint="/api/v2/acc/samples",
    table="acc_stream",
    make_sample=lambda i: {"recordedAt": _recorded_at(i * 20), "accX": 12, "accY": -5, "accZ": 1001 + i},
    value_keys=("accX", "accY", "accZ"),
    out_of_range_value=16_001,
)
STREAMS = pytest.mark.parametrize("stream", [ECG, ACC], ids=lambda s: s.name)


def _batch(
    session_id: object, stream: StreamSpec, count: int = 3, *, batch_id: object | None = None
) -> dict[str, object]:
    """A valid batch. Each call is a NEW logical batch unless `batch_id` is given (a retry)."""
    return {
        "sessionId": str(session_id),
        "batchId": str(batch_id or uuid.uuid4()),
        "samples": [stream.make_sample(i) for i in range(count)],
    }


# --- Fakes -------------------------------------------------------------------


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by sensor-stream tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by sensor-stream tests.")


class FakeSensorStreamRepository(SensorStreamRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed sensor-stream repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number
        self.sessions: dict[uuid.UUID, Session] = {}  # keyed by session_id
        # (stream, athlete_id, session_id, samples) per insert call
        self.inserts: list[tuple[str, str, uuid.UUID, Sequence[object]]] = []
        # Idempotency ledger: (session_id, stream_type, batch_id) -> accepted_count
        self.batches: dict[tuple[uuid.UUID, str, uuid.UUID], int] = {}

    async def claim_batch(
        self,
        *,
        athlete_id: str,
        session_id: uuid.UUID,
        stream_type: str,
        batch_id: uuid.UUID,
        accepted_count: int,
    ) -> bool:
        key = (session_id, stream_type, batch_id)
        if key in self.batches:
            return False
        self.batches[key] = accepted_count
        return True

    async def get_batch_accepted_count(
        self, *, session_id: uuid.UUID, stream_type: str, batch_id: uuid.UUID
    ) -> int | None:
        return self.batches.get((session_id, stream_type, batch_id))

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def get_session_by_id(self, session_id: uuid.UUID) -> Session | None:
        return self.sessions.get(session_id)

    async def insert_ecg_samples(
        self, athlete_id: str, session_id: uuid.UUID, samples: Sequence[EcgSampleRecord]
    ) -> int:
        self.inserts.append(("ecg", athlete_id, session_id, samples))
        return len(samples)

    async def insert_acc_samples(
        self, athlete_id: str, session_id: uuid.UUID, samples: Sequence[AccSampleRecord]
    ) -> int:
        self.inserts.append(("acc", athlete_id, session_id, samples))
        return len(samples)


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_user_repository(user_id: uuid.UUID) -> FakeUserRepository:
    repository = FakeUserRepository()
    repository.users[user_id] = HamsaTechUser(id=user_id, phone_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def fake_sensor_repository() -> FakeSensorStreamRepository:
    repository = FakeSensorStreamRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_sensor_repository: FakeSensorStreamRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_sensor_stream_repository] = lambda: fake_sensor_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_sensor_stream_repository, None)


def _session(athlete_id: str = ATHLETE_ID) -> Session:
    return Session(
        session_id=uuid.uuid4(),
        athlete_id=athlete_id,
        session_type="scoring",
        start_time=utc_now().replace(tzinfo=None),
    )


@pytest.fixture
def owned_session(fake_sensor_repository: FakeSensorStreamRepository) -> Session:
    session = _session()
    fake_sensor_repository.sessions[session.session_id] = session
    return session


def _assert_validation_error(response: Any) -> None:
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    # Error details never carry the submitted sample values back.
    for error in body["error"]["details"]:
        assert set(error) == {"loc", "msg", "type"}


# --- Success path ------------------------------------------------------------


@STREAMS
def test_authenticated_valid_batch_is_accepted(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    response = wired_client.post(
        stream.endpoint, json=_batch(owned_session.session_id, stream, 5), headers=auth_headers
    )

    assert response.status_code == 201
    assert response.json() == {"accepted": 5, "duplicate": False}
    [(inserted_stream, athlete_id, session_id, samples)] = fake_sensor_repository.inserts
    assert inserted_stream == stream.name
    assert athlete_id == ATHLETE_ID
    assert session_id == owned_session.session_id
    assert len(samples) == 5


@STREAMS
def test_snake_case_field_names_are_also_accepted(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    sample = stream.make_sample(0)
    snake = {"recorded_at": sample["recordedAt"]}
    snake.update({_to_snake(k): sample[k] for k in stream.value_keys})
    payload = {
        "session_id": str(owned_session.session_id),
        "batch_id": str(uuid.uuid4()),
        "samples": [snake],
    }

    response = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)

    assert response.status_code == 201
    assert response.json() == {"accepted": 1, "duplicate": False}


def _to_snake(camel: str) -> str:
    return "".join(f"_{c.lower()}" if c.isupper() else c for c in camel)


@STREAMS
def test_maximum_batch_size_is_accepted(
    wired_client: TestClient, auth_headers: dict[str, str], owned_session: Session, stream: StreamSpec
) -> None:
    response = wired_client.post(
        stream.endpoint, json=_batch(owned_session.session_id, stream, MAX_BATCH_SIZE), headers=auth_headers
    )

    assert response.status_code == 201
    assert response.json() == {"accepted": MAX_BATCH_SIZE, "duplicate": False}


# --- Authentication ----------------------------------------------------------


@STREAMS
def test_unauthenticated_request_is_rejected(
    wired_client: TestClient,
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    response = wired_client.post(stream.endpoint, json=_batch(owned_session.session_id, stream))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert fake_sensor_repository.inserts == []


@STREAMS
def test_invalid_token_is_rejected(
    wired_client: TestClient,
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    response = wired_client.post(
        stream.endpoint,
        json=_batch(owned_session.session_id, stream),
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401
    assert fake_sensor_repository.inserts == []


# --- Ownership / identity ----------------------------------------------------


@STREAMS
def test_session_belonging_to_another_athlete_is_forbidden(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    stream: StreamSpec,
) -> None:
    other_session = _session(athlete_id=OTHER_ATHLETE_ID)
    fake_sensor_repository.sessions[other_session.session_id] = other_session

    response = wired_client.post(
        stream.endpoint, json=_batch(other_session.session_id, stream), headers=auth_headers
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert fake_sensor_repository.inserts == []


@STREAMS
def test_athlete_id_in_body_cannot_spoof_ownership(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    stream: StreamSpec,
) -> None:
    """A body-supplied athlete ID never overrides the token's identity — neither to pass the
    ownership check for someone else's session, nor to relabel the stored rows."""
    other_session = _session(athlete_id=OTHER_ATHLETE_ID)
    fake_sensor_repository.sessions[other_session.session_id] = other_session
    spoofed = {
        **_batch(other_session.session_id, stream),
        "athleteId": OTHER_ATHLETE_ID,
        "athlete_id": OTHER_ATHLETE_ID,
    }

    response = wired_client.post(stream.endpoint, json=spoofed, headers=auth_headers)

    assert response.status_code == 403
    assert fake_sensor_repository.inserts == []


@STREAMS
def test_athlete_id_in_body_is_ignored_for_own_session(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    payload = _batch(owned_session.session_id, stream)
    payload["athleteId"] = OTHER_ATHLETE_ID
    for sample in payload["samples"]:  # type: ignore[union-attr]
        sample["athleteId"] = OTHER_ATHLETE_ID

    response = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)

    assert response.status_code == 201
    [(_, athlete_id, _, _)] = fake_sensor_repository.inserts
    assert athlete_id == ATHLETE_ID


@STREAMS
def test_unknown_session_is_not_found(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    stream: StreamSpec,
) -> None:
    response = wired_client.post(stream.endpoint, json=_batch(uuid.uuid4(), stream), headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
    assert fake_sensor_repository.inserts == []


@STREAMS
def test_authenticated_user_without_athlete_profile_is_not_found(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    fake_sensor_repository.athletes.clear()

    response = wired_client.post(
        stream.endpoint, json=_batch(owned_session.session_id, stream), headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"
    assert fake_sensor_repository.inserts == []


# --- Batch / body validation -------------------------------------------------


@STREAMS
@pytest.mark.parametrize("session_id", ["not-a-uuid", "", "12345", None])
def test_invalid_session_uuid_is_rejected(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    stream: StreamSpec,
    session_id: object,
) -> None:
    payload = {"sessionId": session_id, "batchId": str(uuid.uuid4()), "samples": [stream.make_sample(0)]}

    response = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)

    _assert_validation_error(response)
    assert fake_sensor_repository.inserts == []


@STREAMS
def test_missing_session_id_is_rejected(
    wired_client: TestClient, auth_headers: dict[str, str], stream: StreamSpec
) -> None:
    response = wired_client.post(
        stream.endpoint, json={"samples": [stream.make_sample(0)]}, headers=auth_headers
    )

    _assert_validation_error(response)


@STREAMS
def test_empty_sample_array_is_rejected(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    payload = {"sessionId": str(owned_session.session_id), "batchId": str(uuid.uuid4()), "samples": []}

    response = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)

    _assert_validation_error(response)
    assert fake_sensor_repository.inserts == []


@STREAMS
def test_batch_over_maximum_size_is_rejected_without_echoing_samples(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    payload = _batch(owned_session.session_id, stream, MAX_BATCH_SIZE + 1)

    response = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)

    _assert_validation_error(response)
    assert response.json()["error"]["details"][0]["type"] == "too_long"
    assert "recordedAt" not in response.text  # the 5,001 submitted samples are not reflected back
    assert fake_sensor_repository.inserts == []


@STREAMS
def test_body_over_byte_limit_is_rejected(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    oversized = b'{"sessionId": "' + str(owned_session.session_id).encode() + b'", "pad": "'
    oversized += b"x" * MAX_BODY_BYTES + b'"}'

    response = wired_client.post(
        stream.endpoint, content=oversized, headers={**auth_headers, "Content-Type": "application/json"}
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert fake_sensor_repository.inserts == []


@STREAMS
def test_chunked_body_over_byte_limit_is_rejected_without_content_length(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    stream: StreamSpec,
) -> None:
    def chunks() -> Iterator[bytes]:
        yield b'{"pad": "'
        for _ in range(MAX_BODY_BYTES // 65536 + 2):
            yield b"x" * 65536
        yield b'"}'

    response = wired_client.post(
        stream.endpoint, content=chunks(), headers={**auth_headers, "Content-Type": "application/json"}
    )

    assert response.status_code == 413
    assert fake_sensor_repository.inserts == []


@STREAMS
def test_malformed_json_is_rejected(
    wired_client: TestClient, auth_headers: dict[str, str], stream: StreamSpec
) -> None:
    response = wired_client.post(
        stream.endpoint,
        content=b'{"sessionId": ',
        headers={**auth_headers, "Content-Type": "application/json"},
    )

    _assert_validation_error(response)


def _invalid_value_cases(stream: StreamSpec) -> list[object]:
    return [stream.out_of_range_value, -stream.out_of_range_value, 12.5, "123", True, None]


@pytest.mark.parametrize(
    ("stream", "bad_value"),
    [(s, v) for s in (ECG, ACC) for v in _invalid_value_cases(s)],
    ids=lambda p: p.name if isinstance(p, StreamSpec) else repr(p),
)
def test_invalid_sample_value_is_rejected(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
    bad_value: object,
) -> None:
    payload = _batch(owned_session.session_id, stream, 3)
    payload["samples"][1][stream.value_keys[-1]] = bad_value  # type: ignore[index]

    response = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)

    _assert_validation_error(response)
    assert fake_sensor_repository.inserts == []  # one bad sample rejects the whole batch


@STREAMS
def test_sample_missing_a_value_field_is_rejected(
    wired_client: TestClient, auth_headers: dict[str, str], owned_session: Session, stream: StreamSpec
) -> None:
    payload = _batch(owned_session.session_id, stream, 2)
    del payload["samples"][0][stream.value_keys[0]]  # type: ignore[index]

    response = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)

    _assert_validation_error(response)


@STREAMS
@pytest.mark.parametrize(
    "bad_timestamp",
    ["2026-10-05T10:00:00", "not-a-timestamp", "2026-13-45T25:61:00+00:00", 1700000000, ""],
    ids=["naive", "garbage", "impossible-date", "unix-epoch-number", "empty"],
)
def test_invalid_timestamp_is_rejected(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
    bad_timestamp: object,
) -> None:
    payload = _batch(owned_session.session_id, stream, 2)
    payload["samples"][0]["recordedAt"] = bad_timestamp  # type: ignore[index]

    response = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)

    _assert_validation_error(response)
    assert fake_sensor_repository.inserts == []


@STREAMS
def test_boundary_values_are_accepted(
    wired_client: TestClient, auth_headers: dict[str, str], owned_session: Session, stream: StreamSpec
) -> None:
    limit = stream.out_of_range_value - 1
    payload = _batch(owned_session.session_id, stream, 2)
    for key in stream.value_keys:
        payload["samples"][0][key] = limit  # type: ignore[index]
        payload["samples"][1][key] = -limit  # type: ignore[index]

    response = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)

    assert response.status_code == 201


# --- Real repository + real get_db transaction boundary -----------------------


class _FakeResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


class FakeDatabase:
    """
    In-memory stand-in for the database behind the REAL `get_db` + `SensorStreamRepository`.

    Models just enough transactional behavior to test idempotency honestly: each request
    gets its own `FakeAsyncSession` whose writes are pending until `commit()` and vanish on
    `rollback()`; the idempotency ledger enforces its primary key the way PostgreSQL's
    `INSERT ... ON CONFLICT DO NOTHING RETURNING` does (a row comes back only if it was inserted).
    """

    def __init__(self, athlete: HamsaTechAthlete | None, sessions: list[Session]) -> None:
        self.athlete = athlete
        self.sessions = {s.session_id: s for s in sessions}
        self.fail_sample_insert = False
        # Committed state.
        self.ledger: dict[tuple[uuid.UUID, str, uuid.UUID], int] = {}
        self.inserts: list[tuple[str, list[dict[str, Any]]]] = []  # committed sample inserts
        self.commits = 0
        self.rollbacks = 0
        self.statements: list[str] = []  # compiled SQL of every statement, in order

    def session(self) -> "FakeAsyncSession":
        return FakeAsyncSession(self)

    def rows(self, table: str) -> int:
        return sum(len(rows) for name, rows in self.inserts if name == table)


class FakeAsyncSession:
    """One request's transaction against a `FakeDatabase`."""

    def __init__(self, database: FakeDatabase) -> None:
        self._db = database
        self._pending_ledger: dict[tuple[uuid.UUID, str, uuid.UUID], int] = {}
        self._pending_inserts: list[tuple[str, list[dict[str, Any]]]] = []

    async def __aenter__(self) -> "FakeAsyncSession":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def execute(self, statement: Any, params: list[dict[str, Any]] | None = None) -> _FakeResult:
        compiled = statement.compile(dialect=postgresql.dialect())
        self._db.statements.append(str(compiled))
        values = compiled.params

        if isinstance(statement, Insert):
            if statement.table.name == "sensor_ingestion_batches":
                key = (values["session_id"], values["stream_type"], values["batch_id"])
                if key in self._db.ledger or key in self._pending_ledger:
                    return _FakeResult(None)  # ON CONFLICT DO NOTHING → no row returned
                self._pending_ledger[key] = values["accepted_count"]
                return _FakeResult(values["batch_id"])
            if self._db.fail_sample_insert:
                raise RuntimeError("simulated database failure mid-insert")
            self._pending_inserts.append((statement.table.name, list(params or [])))
            return _FakeResult(None)

        assert isinstance(statement, Select)
        entity = statement.column_descriptions[0]["entity"]
        if entity is HamsaTechAthlete:
            return _FakeResult(self._db.athlete)
        if entity is Session:
            return _FakeResult(self._db.sessions.get(values["session_id_1"]))
        assert entity is SensorIngestionBatch
        key = (values["session_id_1"], values["stream_type_1"], values["batch_id_1"])
        return _FakeResult(self._db.ledger.get(key, self._pending_ledger.get(key)))

    async def commit(self) -> None:
        self._db.ledger.update(self._pending_ledger)
        self._db.inserts.extend(self._pending_inserts)
        self._pending_ledger.clear()
        self._pending_inserts.clear()
        self._db.commits += 1

    async def rollback(self) -> None:
        self._pending_ledger.clear()
        self._pending_inserts.clear()
        self._db.rollbacks += 1


@pytest.fixture
def real_repository_client(
    fake_user_repository: FakeUserRepository,
) -> Iterator[TestClient]:
    """A client that keeps the real `get_db` + `SensorStreamRepository` (only user lookup is faked)."""
    test_client = TestClient(fastapi_app, raise_server_exceptions=False)
    fastapi_app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    try:
        yield test_client
    finally:
        fastapi_app.dependency_overrides.pop(get_user_repository, None)


def _install_fake_db(
    monkeypatch: pytest.MonkeyPatch, *, fail_insert: bool = False, extra_sessions: int = 0
) -> tuple[FakeDatabase, Session]:
    session = _session()
    fake_db = FakeDatabase(
        HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER),
        [session, *[_session() for _ in range(extra_sessions)]],
    )
    fake_db.fail_sample_insert = fail_insert
    monkeypatch.setattr("app.dependencies.database.AsyncSessionFactory", fake_db.session)
    return fake_db, session


@STREAMS
def test_batch_is_bulk_inserted_in_one_statement_and_committed_once(
    real_repository_client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    stream: StreamSpec,
) -> None:
    fake_db, session = _install_fake_db(monkeypatch)
    payload = _batch(session.session_id, stream, 250)
    # One sample sent with a +05:30 offset to verify UTC normalization.
    local = datetime(2026, 10, 5, 15, 30, 0, 123456, tzinfo=IST)
    payload["samples"][0]["recordedAt"] = local.isoformat()  # type: ignore[index]

    response = real_repository_client.post(stream.endpoint, json=payload, headers=auth_headers)

    assert response.status_code == 201
    assert response.json() == {"accepted": 250, "duplicate": False}
    [(table, rows)] = fake_db.inserts  # exactly one INSERT statement for the whole batch
    assert table == stream.table
    assert len(rows) == 250
    assert {row["athlete_id"] for row in rows} == {ATHLETE_ID}  # server-derived, never from the body
    assert {row["session_id"] for row in rows} == {session.session_id}
    assert rows[0]["recorded_at"] == datetime(2026, 10, 5, 10, 0, 0, 123456)  # naive UTC
    assert all(row["recorded_at"].tzinfo is None for row in rows)
    assert fake_db.commits == 1
    assert fake_db.rollbacks == 0


@STREAMS
def test_database_failure_rolls_back_the_whole_batch(
    real_repository_client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    stream: StreamSpec,
) -> None:
    fake_db, session = _install_fake_db(monkeypatch, fail_insert=True)

    response = real_repository_client.post(
        stream.endpoint, json=_batch(session.session_id, stream, 50), headers=auth_headers
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "simulated database failure" not in response.text
    assert fake_db.inserts == []
    assert fake_db.rollbacks == 1
    assert fake_db.commits == 0


# --- Rate limiting -----------------------------------------------------------


def _request_with_headers(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("203.0.113.7", 12345),
    }
    return Request(scope)


def test_rate_limit_key_is_per_caller_and_never_the_raw_token() -> None:
    token_a = create_access_token(uuid.uuid4())
    token_b = create_access_token(uuid.uuid4())

    key_a = authenticated_caller_key(_request_with_headers({"Authorization": f"Bearer {token_a}"}))
    key_b = authenticated_caller_key(_request_with_headers({"Authorization": f"Bearer {token_b}"}))

    assert key_a != key_b
    assert token_a not in key_a
    assert key_a.startswith("bearer:")


def test_rate_limit_key_falls_back_to_client_ip_without_a_bearer_token() -> None:
    assert authenticated_caller_key(_request_with_headers({})) == "203.0.113.7"
    assert authenticated_caller_key(_request_with_headers({"Authorization": "Basic abc"})) == "203.0.113.7"


def test_sensor_routes_declare_their_own_limits() -> None:
    route_limits = limiter._route_limits
    for name in (
        "app.modules.sensor_streams.routers.ecg_router.record_ecg_samples",
        "app.modules.sensor_streams.routers.acc_router.record_acc_samples",
    ):
        assert sorted(str(limit.limit) for limit in route_limits[name]) == [
            "120 per 1 minute",
            "1200 per 1 minute",
        ]


@pytest.mark.skipif(not limiter.enabled, reason="rate limiting disabled in this environment")
def test_per_caller_limit_is_enforced(
    wired_client: TestClient, auth_headers: dict[str, str], owned_session: Session
) -> None:
    allowed = int(PER_CALLER_LIMIT.split("/")[0])
    payload = _batch(owned_session.session_id, ECG, 1)

    statuses = [
        wired_client.post(ECG.endpoint, json=payload, headers=auth_headers).status_code
        for _ in range(allowed)
    ]
    blocked = wired_client.post(ECG.endpoint, json=payload, headers=auth_headers)

    assert statuses == [201] * allowed
    assert blocked.status_code == 429


@pytest.mark.skipif(not limiter.enabled, reason="rate limiting disabled in this environment")
def test_per_caller_limit_does_not_throttle_other_athletes_on_the_same_ip(
    wired_client: TestClient,
    fake_user_repository: FakeUserRepository,
    auth_headers: dict[str, str],
    owned_session: Session,
) -> None:
    allowed = int(PER_CALLER_LIMIT.split("/")[0])
    payload = _batch(owned_session.session_id, ACC, 1)
    for _ in range(allowed + 1):
        wired_client.post(ACC.endpoint, json=payload, headers=auth_headers)

    # A second user (same IP, same TestClient) with their own token is unaffected.
    other_user_id = uuid.uuid4()
    fake_user_repository.users[other_user_id] = HamsaTechUser(id=other_user_id, phone_number=PHONE_NUMBER)
    other_headers = {"Authorization": f"Bearer {create_access_token(other_user_id)}"}

    response = wired_client.post(ACC.endpoint, json=payload, headers=other_headers)

    assert response.status_code == 201


def test_utc_offset_normalization_is_independent_of_server_timezone() -> None:
    """Sanity check of the storage convention the repository applies (aware → naive UTC)."""
    from app.modules.sensor_streams.repositories.sensor_stream_repository import _to_naive_utc

    assert _to_naive_utc(datetime(2026, 1, 1, 5, 30, tzinfo=IST)) == datetime(2026, 1, 1, 0, 0)
    assert _to_naive_utc(datetime(2026, 1, 1, 0, 0, tzinfo=UTC)) == datetime(2026, 1, 1, 0, 0)


# --- Batch idempotency (batchId) ----------------------------------------------
#
# A client retries a batch whose response it never received. The retry carries
# the same batchId, and must never store the samples a second time.


@STREAMS
def test_same_batch_id_submitted_twice_is_stored_once(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    payload = _batch(owned_session.session_id, stream, 7)

    first = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)
    second = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)
    third = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)

    assert first.status_code == 201
    assert first.json() == {"accepted": 7, "duplicate": False}
    for retry in (second, third):
        assert retry.status_code == 201  # a retry is a success, not an error
        assert retry.json() == {"accepted": 7, "duplicate": True}  # the ORIGINAL count
    assert len(fake_sensor_repository.inserts) == 1  # zero additional rows


@STREAMS
def test_different_batch_ids_are_stored_separately(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    for _ in range(3):
        response = wired_client.post(
            stream.endpoint, json=_batch(owned_session.session_id, stream, 4), headers=auth_headers
        )
        assert response.json() == {"accepted": 4, "duplicate": False}

    assert len(fake_sensor_repository.inserts) == 3


def test_same_uuid_on_ecg_and_acc_are_two_different_batches(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
) -> None:
    shared_id = uuid.uuid4()

    ecg = wired_client.post(
        ECG.endpoint, json=_batch(owned_session.session_id, ECG, 5, batch_id=shared_id), headers=auth_headers
    )
    acc = wired_client.post(
        ACC.endpoint, json=_batch(owned_session.session_id, ACC, 6, batch_id=shared_id), headers=auth_headers
    )

    assert ecg.json() == {"accepted": 5, "duplicate": False}
    assert acc.json() == {"accepted": 6, "duplicate": False}
    assert [stream for stream, *_ in fake_sensor_repository.inserts] == ["ecg", "acc"]


@STREAMS
def test_same_batch_id_in_another_own_session_is_an_independent_batch(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    """Batch ids are scoped to a session: reusing one in a different session the caller owns
    neither replays the first session's result nor loses the second session's samples."""
    second_session = _session()
    fake_sensor_repository.sessions[second_session.session_id] = second_session
    shared_id = uuid.uuid4()

    first = wired_client.post(
        stream.endpoint,
        json=_batch(owned_session.session_id, stream, 3, batch_id=shared_id),
        headers=auth_headers,
    )
    second = wired_client.post(
        stream.endpoint,
        json=_batch(second_session.session_id, stream, 9, batch_id=shared_id),
        headers=auth_headers,
    )

    assert first.json() == {"accepted": 3, "duplicate": False}
    assert second.json() == {"accepted": 9, "duplicate": False}
    assert [session_id for _, _, session_id, _ in fake_sensor_repository.inserts] == [
        owned_session.session_id,
        second_session.session_id,
    ]


@STREAMS
def test_known_batch_id_cannot_bypass_session_ownership(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    stream: StreamSpec,
) -> None:
    """A batch id another athlete already used buys nothing: for a session the caller does not
    own the request is refused before the ledger is consulted — no replayed count, no claim."""
    victim_session = _session(athlete_id=OTHER_ATHLETE_ID)
    fake_sensor_repository.sessions[victim_session.session_id] = victim_session
    victim_batch_id = uuid.uuid4()
    stream_type = stream.name.upper()
    fake_sensor_repository.batches[(victim_session.session_id, stream_type, victim_batch_id)] = 42

    response = wired_client.post(
        stream.endpoint,
        json=_batch(victim_session.session_id, stream, 42, batch_id=victim_batch_id),
        headers=auth_headers,
    )

    assert response.status_code == 403
    assert "accepted" not in response.text  # the victim's count is not disclosed
    assert fake_sensor_repository.inserts == []
    assert fake_sensor_repository.batches == {(victim_session.session_id, stream_type, victim_batch_id): 42}


@STREAMS
def test_another_athletes_batch_id_does_not_interfere_with_own_session(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    """The same UUID already recorded for another athlete's session neither blocks nor
    short-circuits this athlete's own batch."""
    victim_session = _session(athlete_id=OTHER_ATHLETE_ID)
    shared_id = uuid.uuid4()
    fake_sensor_repository.batches[(victim_session.session_id, stream.name.upper(), shared_id)] = 42

    response = wired_client.post(
        stream.endpoint,
        json=_batch(owned_session.session_id, stream, 5, batch_id=shared_id),
        headers=auth_headers,
    )

    assert response.json() == {"accepted": 5, "duplicate": False}
    [(_, athlete_id, session_id, _)] = fake_sensor_repository.inserts
    assert (athlete_id, session_id) == (ATHLETE_ID, owned_session.session_id)


@STREAMS
def test_batch_id_reused_with_different_contents_is_a_conflict(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    batch_id = uuid.uuid4()
    wired_client.post(
        stream.endpoint,
        json=_batch(owned_session.session_id, stream, 5, batch_id=batch_id),
        headers=auth_headers,
    )

    response = wired_client.post(
        stream.endpoint,
        json=_batch(owned_session.session_id, stream, 8, batch_id=batch_id),
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "BATCH_ID_REUSED"
    assert len(fake_sensor_repository.inserts) == 1  # the different batch was not stored under the old id


@STREAMS
@pytest.mark.parametrize("batch_id", ["not-a-uuid", "", 12345, None])
def test_invalid_batch_id_is_rejected(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
    batch_id: object,
) -> None:
    payload = _batch(owned_session.session_id, stream)
    payload["batchId"] = batch_id

    response = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)

    _assert_validation_error(response)
    assert fake_sensor_repository.batches == {}


@STREAMS
def test_missing_batch_id_is_rejected(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    payload = _batch(owned_session.session_id, stream)
    del payload["batchId"]

    response = wired_client.post(stream.endpoint, json=payload, headers=auth_headers)

    _assert_validation_error(response)
    assert fake_sensor_repository.inserts == []


@STREAMS
def test_rejected_requests_never_claim_a_batch_id(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_sensor_repository: FakeSensorStreamRepository,
    owned_session: Session,
    stream: StreamSpec,
) -> None:
    """Validation (422), authentication (401) and unknown-session (404) failures happen before
    the ledger, so the same batchId can still be submitted correctly afterwards."""
    batch_id = uuid.uuid4()
    invalid = _batch(owned_session.session_id, stream, 3, batch_id=batch_id)
    invalid["samples"][0][stream.value_keys[0]] = stream.out_of_range_value  # type: ignore[index]

    assert wired_client.post(stream.endpoint, json=invalid, headers=auth_headers).status_code == 422
    assert (
        wired_client.post(
            stream.endpoint, json=_batch(owned_session.session_id, stream, 3, batch_id=batch_id)
        ).status_code
        == 401
    )
    assert (
        wired_client.post(
            stream.endpoint, json=_batch(uuid.uuid4(), stream, 3, batch_id=batch_id), headers=auth_headers
        ).status_code
        == 404
    )
    assert fake_sensor_repository.batches == {}

    valid = wired_client.post(
        stream.endpoint,
        json=_batch(owned_session.session_id, stream, 3, batch_id=batch_id),
        headers=auth_headers,
    )
    assert valid.json() == {"accepted": 3, "duplicate": False}


# --- Idempotency through the REAL repository and REAL get_db transaction -------


@STREAMS
def test_claim_is_one_atomic_insert_on_conflict_not_select_then_insert(
    real_repository_client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    stream: StreamSpec,
) -> None:
    fake_db, session = _install_fake_db(monkeypatch)

    real_repository_client.post(
        stream.endpoint, json=_batch(session.session_id, stream, 5), headers=auth_headers
    )

    ledger_statements = [sql for sql in fake_db.statements if "sensor_ingestion_batches" in sql]
    [claim] = ledger_statements  # a first request never SELECTs the ledger
    assert claim.startswith("INSERT INTO hamsatech.sensor_ingestion_batches")
    assert "ON CONFLICT (session_id, stream_type, batch_id) DO NOTHING" in claim
    assert "RETURNING" in claim
    # The claim precedes the sample insert, inside the same (single) transaction.
    order = [sql.split()[0] + " " + sql.split()[2] for sql in fake_db.statements if sql.startswith("INSERT")]
    assert order == ["INSERT hamsatech.sensor_ingestion_batches", f"INSERT hamsatech.{stream.table}"]
    assert fake_db.commits == 1


@STREAMS
def test_response_lost_then_retry_stores_no_duplicate_rows(
    real_repository_client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    stream: StreamSpec,
) -> None:
    """Regression: backend commits the batch → HTTP response is lost → client retries the same
    batch → NO duplicate rows, and the retry is answered with the original accepted count."""
    fake_db, session = _install_fake_db(monkeypatch)
    payload = _batch(session.session_id, stream, 130)

    committed = real_repository_client.post(stream.endpoint, json=payload, headers=auth_headers)
    assert committed.status_code == 201  # ...but imagine the client never received this
    assert fake_db.rows(stream.table) == 130

    retry = real_repository_client.post(stream.endpoint, json=payload, headers=auth_headers)

    assert retry.status_code == 201
    assert retry.json() == {"accepted": 130, "duplicate": True}
    assert fake_db.rows(stream.table) == 130  # not 260
    assert len(fake_db.ledger) == 1
    retry_statements = fake_db.statements[len(fake_db.statements) // 2 :]
    assert not any(sql.startswith(f"INSERT INTO hamsatech.{stream.table}") for sql in retry_statements)


@STREAMS
def test_failed_sample_insert_rolls_back_the_batch_marker_so_a_retry_succeeds(
    real_repository_client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    stream: StreamSpec,
) -> None:
    fake_db, session = _install_fake_db(monkeypatch, fail_insert=True)
    payload = _batch(session.session_id, stream, 40)

    failed = real_repository_client.post(stream.endpoint, json=payload, headers=auth_headers)

    assert failed.status_code == 500
    assert fake_db.rollbacks == 1
    assert fake_db.ledger == {}  # the claim did not survive the rollback
    assert fake_db.rows(stream.table) == 0

    fake_db.fail_sample_insert = False
    retry = real_repository_client.post(stream.endpoint, json=payload, headers=auth_headers)

    assert retry.json() == {"accepted": 40, "duplicate": False}  # processed as a first request
    assert fake_db.rows(stream.table) == 40
    assert len(fake_db.ledger) == 1


def test_same_uuid_for_ecg_and_acc_through_the_real_repository(
    real_repository_client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_db, session = _install_fake_db(monkeypatch)
    shared_id = uuid.uuid4()

    for stream in (ECG, ACC, ECG, ACC):  # each sent twice
        real_repository_client.post(
            stream.endpoint,
            json=_batch(session.session_id, stream, 10, batch_id=shared_id),
            headers=auth_headers,
        )

    assert fake_db.rows("ecg_stream") == 10
    assert fake_db.rows("acc_stream") == 10
    assert sorted(stream_type for _, stream_type, _ in fake_db.ledger) == ["ACC", "ECG"]


async def test_concurrent_duplicates_insert_the_batch_only_once() -> None:
    """Two identical requests racing through the service: the ledger's uniqueness lets exactly
    one of them insert. (PostgreSQL's blocking behavior itself is covered by
    tests/integration/test_sensor_idempotency_postgres.py.)"""
    import asyncio
    import json

    from app.modules.sensor_streams.schemas import EcgSampleBatchRequest
    from app.modules.sensor_streams.services.sensor_stream_service import SensorStreamService

    class RacingRepository(FakeSensorStreamRepository):
        async def insert_ecg_samples(
            self, athlete_id: str, session_id: uuid.UUID, samples: Sequence[EcgSampleRecord]
        ) -> int:
            await asyncio.sleep(0.01)  # hold the "transaction" open so the requests overlap
            return await super().insert_ecg_samples(athlete_id, session_id, samples)

    repository = RacingRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER)
    session = _session()
    repository.sessions[session.session_id] = session
    payload = EcgSampleBatchRequest.model_validate_json(json.dumps(_batch(session.session_id, ECG, 25)))
    service = SensorStreamService(repository)

    results = await asyncio.gather(*(service.record_ecg_samples(PHONE_NUMBER, payload) for _ in range(5)))

    assert len(repository.inserts) == 1
    assert sorted(r.duplicate for r in results) == [False, True, True, True, True]
    assert {r.accepted for r in results} == {25}
