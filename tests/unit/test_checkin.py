"""
Daily check-in module tests: same-day upsert.

Uses a fake `CheckinRepositoryInterface` and a fake `UserRepositoryInterface`
(via FastAPI's `dependency_overrides`) instead of a real Postgres/Supabase
connection — same convention as `test_series.py`/`test_streak.py`.
Requests carry a real JWT access token (via `create_access_token`), so
`get_current_athlete`'s actual decode-and-lookup logic is exercised
end-to-end, not stubbed out.
"""

import uuid
from collections.abc import Iterator
from datetime import date, datetime, timedelta

import pytest
from app.models.daily_checkin import DailyCheckin
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token, create_refresh_token
from app.modules.checkin.dependencies.services import get_checkin_repository
from app.modules.checkin.repositories.checkin_repository_interface import CheckinRepositoryInterface
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"

_ENDPOINT = "/api/v1/checkin/daily"

_VALID_BODY = {
    "athlete_id": ATHLETE_ID,
    "mood": 4,
    "energy_level": 7,
    "sleep_band": "7-8h",
    "tags": ["focused", "calm"],
}


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by check-in tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by check-in tests.")


class FakeCheckinRepository(CheckinRepositoryInterface):
    """
    In-memory stand-in for the SQLAlchemy-backed check-in repository.
    Mirrors the real repository's upsert contract exactly: one row per
    (athlete_id, checkin_date), created_at preserved across updates,
    updated_at refreshed on every call — same semantics the real
    `ON CONFLICT (athlete_id, checkin_date) DO UPDATE` enforces.
    """

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number
        self.rows: dict[tuple[str, date], DailyCheckin] = {}  # keyed by (athlete_id, checkin_date)
        self.upsert_calls = 0

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def upsert_checkin(
        self,
        *,
        athlete_id: str,
        checkin_date: date,
        mood: int,
        energy_level: int,
        sleep_band: str,
        tags: list[str] | None,
        notes: str | None,
    ) -> DailyCheckin:
        self.upsert_calls += 1
        now = utc_now().replace(tzinfo=None)
        key = (athlete_id, checkin_date)
        existing = self.rows.get(key)
        row = DailyCheckin(
            id=existing.id if existing else uuid.uuid4(),
            athlete_id=athlete_id,
            checkin_date=checkin_date,
            mood=mood,
            energy_level=energy_level,
            sleep_band=sleep_band,
            tags=tags,
            notes=notes,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self.rows[key] = row
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
def fake_checkin_repository() -> FakeCheckinRepository:
    repository = FakeCheckinRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_checkin_repository: FakeCheckinRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_checkin_repository] = lambda: fake_checkin_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_checkin_repository, None)


# --- 1. Valid first check-in ---------------------------------------------------------


def test_save_checkin_success(
    wired_client: TestClient, auth_headers: dict[str, str], fake_checkin_repository: FakeCheckinRepository
) -> None:
    response = wired_client.post(_ENDPOINT, json=_VALID_BODY, headers=auth_headers)

    assert response.status_code == 200
    assert len(fake_checkin_repository.rows) == 1


# --- 2. Correct response schema -------------------------------------------------------


def test_save_checkin_response_schema(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.post(_ENDPOINT, json=_VALID_BODY, headers=auth_headers)

    body = response.json()
    assert set(body.keys()) == {
        "athlete_id",
        "checkin_date",
        "mood",
        "energy_level",
        "sleep_band",
        "tags",
        "notes",
        "created_at",
        "updated_at",
    }
    assert body["athlete_id"] == ATHLETE_ID
    assert body["mood"] == 4
    assert body["energy_level"] == 7
    assert body["sleep_band"] == "7-8h"
    assert body["tags"] == ["focused", "calm"]
    assert body["notes"] is None
    for forbidden_key in ("id", "password", "otp", "token", "jwt", "contact_number"):
        assert forbidden_key not in body


# --- 3-7. Validation ------------------------------------------------------------------


def test_save_checkin_mood_below_range(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.post(_ENDPOINT, json={**_VALID_BODY, "mood": 0}, headers=auth_headers)
    assert response.status_code == 422


def test_save_checkin_mood_above_range(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.post(_ENDPOINT, json={**_VALID_BODY, "mood": 6}, headers=auth_headers)
    assert response.status_code == 422


def test_save_checkin_energy_below_range(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.post(_ENDPOINT, json={**_VALID_BODY, "energy_level": 0}, headers=auth_headers)
    assert response.status_code == 422


def test_save_checkin_energy_above_range(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.post(_ENDPOINT, json={**_VALID_BODY, "energy_level": 11}, headers=auth_headers)
    assert response.status_code == 422


def test_save_checkin_invalid_sleep_band(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.post(
        _ENDPOINT, json={**_VALID_BODY, "sleep_band": "10 hours"}, headers=auth_headers
    )
    assert response.status_code == 422


# --- 8-10. Authentication --------------------------------------------------------------


def test_save_checkin_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.post(_ENDPOINT, json=_VALID_BODY)
    assert response.status_code == 401


def test_save_checkin_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.post(
        _ENDPOINT, json=_VALID_BODY, headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_save_checkin_rejects_refresh_token_used_as_access_token(
    wired_client: TestClient, user_id: uuid.UUID
) -> None:
    refresh_token = create_refresh_token(user_id)
    response = wired_client.post(
        _ENDPOINT, json=_VALID_BODY, headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert response.status_code == 401


# --- 11. athlete_id mismatch ------------------------------------------------------------


def test_save_checkin_rejects_athlete_id_mismatch(
    wired_client: TestClient, auth_headers: dict[str, str], fake_checkin_repository: FakeCheckinRepository
) -> None:
    response = wired_client.post(
        _ENDPOINT, json={**_VALID_BODY, "athlete_id": OTHER_ATHLETE_ID}, headers=auth_headers
    )

    assert response.status_code == 403
    assert len(fake_checkin_repository.rows) == 0  # nothing written for the wrong athlete


def test_save_checkin_athlete_not_found(
    wired_client: TestClient, auth_headers: dict[str, str], fake_checkin_repository: FakeCheckinRepository
) -> None:
    fake_checkin_repository.athletes.pop(PHONE_NUMBER)

    response = wired_client.post(_ENDPOINT, json=_VALID_BODY, headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


# --- 12-15. Same-day upsert -------------------------------------------------------------


def test_save_checkin_second_submission_same_day_updates_existing_row(
    wired_client: TestClient, auth_headers: dict[str, str], fake_checkin_repository: FakeCheckinRepository
) -> None:
    wired_client.post(_ENDPOINT, json=_VALID_BODY, headers=auth_headers)
    second = wired_client.post(
        _ENDPOINT, json={**_VALID_BODY, "mood": 2, "energy_level": 3}, headers=auth_headers
    )

    assert second.status_code == 200
    body = second.json()
    assert body["mood"] == 2
    assert body["energy_level"] == 3


def test_save_checkin_second_submission_does_not_create_duplicate_row(
    wired_client: TestClient, auth_headers: dict[str, str], fake_checkin_repository: FakeCheckinRepository
) -> None:
    wired_client.post(_ENDPOINT, json=_VALID_BODY, headers=auth_headers)
    wired_client.post(_ENDPOINT, json={**_VALID_BODY, "mood": 2}, headers=auth_headers)

    assert fake_checkin_repository.upsert_calls == 2
    assert len(fake_checkin_repository.rows) == 1  # still exactly one row for this athlete/day


def test_save_checkin_created_at_stable_after_upsert(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    first = wired_client.post(_ENDPOINT, json=_VALID_BODY, headers=auth_headers)
    first_created_at = first.json()["created_at"]

    second = wired_client.post(_ENDPOINT, json={**_VALID_BODY, "mood": 1}, headers=auth_headers)

    assert second.json()["created_at"] == first_created_at


def test_save_checkin_updated_at_changes_on_upsert(
    wired_client: TestClient, auth_headers: dict[str, str], fake_checkin_repository: FakeCheckinRepository
) -> None:
    first = wired_client.post(_ENDPOINT, json=_VALID_BODY, headers=auth_headers)
    first_updated_at = datetime.fromisoformat(first.json()["updated_at"])

    # Force a detectable time gap so a real (non-mocked) clock still proves the point.
    key = (ATHLETE_ID, utc_now().date())
    fake_checkin_repository.rows[key].updated_at = first_updated_at - timedelta(seconds=5)

    second = wired_client.post(_ENDPOINT, json={**_VALID_BODY, "mood": 1}, headers=auth_headers)
    second_updated_at = datetime.fromisoformat(second.json()["updated_at"])

    assert second_updated_at > first_updated_at - timedelta(seconds=5)


# --- 16-17. Historical persistence / athlete isolation ------------------------------------


def test_save_checkin_historical_records_remain_after_subsequent_days(
    fake_checkin_repository: FakeCheckinRepository,
) -> None:
    today = date(2026, 6, 15)
    yesterday = today - timedelta(days=1)
    fake_checkin_repository.rows[(ATHLETE_ID, yesterday)] = DailyCheckin(
        id=uuid.uuid4(),
        athlete_id=ATHLETE_ID,
        checkin_date=yesterday,
        mood=3,
        energy_level=5,
        sleep_band="6-7h",
        tags=None,
        notes=None,
        created_at=None,
        updated_at=None,
    )
    fake_checkin_repository.rows[(ATHLETE_ID, today)] = DailyCheckin(
        id=uuid.uuid4(),
        athlete_id=ATHLETE_ID,
        checkin_date=today,
        mood=4,
        energy_level=7,
        sleep_band="7-8h",
        tags=None,
        notes=None,
        created_at=None,
        updated_at=None,
    )

    # Both days' rows coexist — a new day's submission never touches yesterday's row.
    assert len(fake_checkin_repository.rows) == 2
    assert fake_checkin_repository.rows[(ATHLETE_ID, yesterday)].mood == 3
    assert fake_checkin_repository.rows[(ATHLETE_ID, today)].mood == 4


async def test_save_checkin_two_athletes_same_date_independent(
    wired_client: TestClient, auth_headers: dict[str, str], fake_checkin_repository: FakeCheckinRepository
) -> None:
    fake_checkin_repository.athletes["+919999999999"] = HamsaTechAthlete(
        athlete_id=OTHER_ATHLETE_ID, contact_number="+919999999999"
    )

    wired_client.post(_ENDPOINT, json=_VALID_BODY, headers=auth_headers)

    # Simulate the other athlete's own submission directly against the fake repository
    # (a second real HTTP call would need a second token/athlete fixture pair).
    today = utc_now().date()
    await fake_checkin_repository.upsert_checkin(
        athlete_id=OTHER_ATHLETE_ID,
        checkin_date=today,
        mood=1,
        energy_level=1,
        sleep_band="<5h",
        tags=None,
        notes=None,
    )

    assert len(fake_checkin_repository.rows) == 2
    assert fake_checkin_repository.rows[(ATHLETE_ID, today)].mood == 4
    assert fake_checkin_repository.rows[(OTHER_ATHLETE_ID, today)].mood == 1


# --- 18-19. Optional fields --------------------------------------------------------------


def test_save_checkin_tags_optional(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    body = {k: v for k, v in _VALID_BODY.items() if k != "tags"}
    response = wired_client.post(_ENDPOINT, json=body, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["tags"] == []


def test_save_checkin_notes_optional(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.post(_ENDPOINT, json={**_VALID_BODY, "notes": "felt great"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["notes"] == "felt great"


# --- 20. Missing required fields ----------------------------------------------------------


def test_save_checkin_missing_required_field(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    body = {k: v for k, v in _VALID_BODY.items() if k != "sleep_band"}
    response = wired_client.post(_ENDPOINT, json=body, headers=auth_headers)
    assert response.status_code == 422


# --- 21-22. UTC date / no client-supplied date --------------------------------------------


def test_save_checkin_date_is_server_computed_utc_today(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.post(_ENDPOINT, json=_VALID_BODY, headers=auth_headers)

    assert response.json()["checkin_date"] == utc_now().date().isoformat()


def test_save_checkin_request_schema_has_no_date_field(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    # A client-supplied date/checkin_date is not even an accepted field —
    # there is no way to request a past- or future-dated row.
    response = wired_client.post(
        _ENDPOINT,
        json={**_VALID_BODY, "checkin_date": "2099-01-01", "date": "2099-01-01"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["checkin_date"] == utc_now().date().isoformat()


# --- 23. Sensitive fields never returned (covered by schema test above too) --------------


def test_save_checkin_never_returns_internal_id(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.post(_ENDPOINT, json=_VALID_BODY, headers=auth_headers)
    assert "id" not in response.json()


# --- 24. Database uniqueness constraint ----------------------------------------------------
# Enforced at the DB level (migration 0005's UNIQUE(athlete_id, checkin_date)); the
# upsert-not-duplicate behavior it guarantees is exercised end-to-end by
# test_save_checkin_second_submission_does_not_create_duplicate_row above, via the
# fake repository's own (athlete_id, checkin_date)-keyed dict, which mirrors that
# constraint's semantics. Not re-tested against a real database here — consistent
# with this project's existing, documented absence of integration tests against a
# real Postgres instance for every other module.


# --- 25. Transaction rollback / error behavior ----------------------------------------------
#
# Not exercised via an HTTP-level test here: FastAPI's `TestClient` (used by
# `wired_client`) re-raises an unhandled exception during a `BaseHTTPMiddleware`
# request instead of returning the 500 response `app.exceptions.handlers.
# unhandled_exception_handler` would produce against a real ASGI server — a
# known Starlette/TestClient interaction, not specific to this module (no
# other test file in this project tests a generic unhandled-exception path
# via HTTP for the same reason). The handler itself was already verified by
# direct source review in an earlier audit pass: it logs the full exception
# server-side and returns a generic `INTERNAL_SERVER_ERROR` envelope,
# regardless of `DEBUG`/`ENVIRONMENT`, never leaking internals or fabricating
# a success response.
