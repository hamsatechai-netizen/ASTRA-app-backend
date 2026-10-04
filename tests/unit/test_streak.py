"""
Streak module tests: current/longest streak calculation.

Uses a fake `StreakRepositoryInterface` and a fake `UserRepositoryInterface`
(via FastAPI's `dependency_overrides`) instead of a real Postgres/Supabase
connection — same convention as `test_dashboard.py`/`test_session_history.py`.
Requests carry a real JWT access token (via `create_access_token`), so
`get_current_athlete`'s actual decode-and-lookup logic is exercised
end-to-end, not stubbed out.

Test matrix mirrors the one produced in the Streak audit/specification
pass: no sessions, today, yesterday, two days ago, consecutive runs, a
gap breaking the current streak while preserving the longest, duplicate
dates, and future dates never participating.
"""

import uuid
from collections.abc import Iterator, Sequence
from datetime import date, timedelta

import pytest
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token, create_refresh_token
from app.modules.streak.dependencies.services import get_streak_repository
from app.modules.streak.repositories.streak_repository_interface import StreakRepositoryInterface
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
OTHER_ATHLETE_ID = "ASA002"

# Fixed "today" used only by the pure `_compute_streaks` tests below, which
# take `today` as an explicit parameter — safe to pin, no wall-clock
# dependency. HTTP-level tests further down call the real service, which
# uses `utc_now().date()` internally, so they compute dates relative to the
# *actual* current date instead (via `_real_days_ago`), never this constant.
TODAY = date(2026, 6, 15)  # Monday
YESTERDAY = TODAY - timedelta(days=1)


def _streak_endpoint(athlete_id: str) -> str:
    return f"/api/mobile/athletes/{athlete_id}/streak"


class FakeUserRepository(UserRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed user repository."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return next((u for u in self.users.values() if u.phone_number == phone_number), None)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return self.users.get(user_id)

    async def create(self, phone_number: str) -> HamsaTechUser:
        raise NotImplementedError("Not exercised by streak tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by streak tests.")


class FakeStreakRepository(StreakRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed streak repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number
        self.dates_by_athlete: dict[str, list[date]] = {}  # unsorted, may include "future" dates

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def get_completed_session_dates(self, athlete_id: str, on_or_before: date) -> Sequence[date]:
        raw = self.dates_by_athlete.get(athlete_id, [])
        distinct_valid = {d for d in raw if d <= on_or_before}
        return sorted(distinct_valid, reverse=True)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_user_repository(user_id: uuid.UUID) -> FakeUserRepository:
    repository = FakeUserRepository()
    repository.users[user_id] = HamsaTechUser(id=user_id, phone_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def fake_streak_repository() -> FakeStreakRepository:
    repository = FakeStreakRepository()
    repository.athletes[PHONE_NUMBER] = HamsaTechAthlete(athlete_id=ATHLETE_ID, contact_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_streak_repository: FakeStreakRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_streak_repository] = lambda: fake_streak_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_streak_repository, None)


def _days_ago(n: int) -> date:
    """For the pure `_compute_streaks(dates, TODAY)` tests only."""
    return TODAY - timedelta(days=n)


def _real_days_ago(n: int) -> date:
    """
    For HTTP-level tests: relative to the actual current date, matching
    what `StreakService.get_streak` computes internally via `utc_now()`.
    Using the fixed `TODAY` constant here would silently desync from
    whatever "today" the real service sees and produce wrong expectations.
    """
    return utc_now().date() - timedelta(days=n)


# --- GET /api/mobile/athletes/{athlete_id}/streak -----------------------------------


def test_streak_no_sessions(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.get(_streak_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "athlete_id": ATHLETE_ID,
        "current_streak": 0,
        "longest_streak": 0,
        "last_active_date": None,
    }


def test_streak_schema_has_no_sensitive_or_fabricated_fields(
    wired_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = wired_client.get(_streak_endpoint(ATHLETE_ID), headers=auth_headers)

    body = response.json()
    assert set(body.keys()) == {"athlete_id", "current_streak", "longest_streak", "last_active_date"}
    for forbidden_key in ("password", "otp", "token", "jwt", "contact_number", "readiness", "recovery"):
        assert forbidden_key not in body


def test_streak_future_dated_session_never_participates(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_streak_repository: FakeStreakRepository,
) -> None:
    # A future date would never actually reach the service (the repository
    # contract excludes anything after `on_or_before`), but this proves the
    # fake honors that contract exactly like the real repository must.
    fake_streak_repository.dates_by_athlete[ATHLETE_ID] = [_real_days_ago(-5)]  # 5 days in the future

    response = wired_client.get(_streak_endpoint(ATHLETE_ID), headers=auth_headers)

    body = response.json()
    assert body["current_streak"] == 0
    assert body["longest_streak"] == 0
    assert body["last_active_date"] is None


def test_streak_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.get(_streak_endpoint(ATHLETE_ID))
    assert response.status_code == 401


def test_streak_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.get(
        _streak_endpoint(ATHLETE_ID), headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_streak_rejects_refresh_token_used_as_access_token(
    wired_client: TestClient, user_id: uuid.UUID
) -> None:
    refresh_token = create_refresh_token(user_id)
    response = wired_client.get(
        _streak_endpoint(ATHLETE_ID), headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert response.status_code == 401


def test_streak_rejects_mismatched_athlete_id(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.get(_streak_endpoint(OTHER_ATHLETE_ID), headers=auth_headers)
    assert response.status_code == 403


def test_streak_athlete_not_found(
    wired_client: TestClient, auth_headers: dict[str, str], fake_streak_repository: FakeStreakRepository
) -> None:
    fake_streak_repository.athletes.pop(PHONE_NUMBER)

    response = wired_client.get(_streak_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


def test_streak_isolated_per_athlete(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_streak_repository: FakeStreakRepository,
) -> None:
    fake_streak_repository.dates_by_athlete[ATHLETE_ID] = []
    fake_streak_repository.dates_by_athlete[OTHER_ATHLETE_ID] = [
        _real_days_ago(0),
        _real_days_ago(1),
        _real_days_ago(2),
    ]

    response = wired_client.get(_streak_endpoint(ATHLETE_ID), headers=auth_headers)

    assert response.json()["current_streak"] == 0


def test_streak_duplicate_same_day_sessions_count_once(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_streak_repository: FakeStreakRepository,
) -> None:
    """
    Two (or more) sessions on the same calendar day must not inflate the
    streak. The real repository guarantees this with `SELECT DISTINCT`;
    `FakeStreakRepository.get_completed_session_dates` mirrors that exact
    de-duplication so this test exercises the same contract the real one
    must uphold.
    """
    fake_streak_repository.dates_by_athlete[ATHLETE_ID] = [
        _real_days_ago(0),
        _real_days_ago(0),  # duplicate — same session or a second session, same day
        _real_days_ago(1),
    ]

    response = wired_client.get(_streak_endpoint(ATHLETE_ID), headers=auth_headers)

    body = response.json()
    assert body["current_streak"] == 2
    assert body["longest_streak"] == 2


# --- Pure calculation coverage, via the service function directly ------------------
# The HTTP-level tests above prove wiring/auth/isolation; these prove the
# calculation itself against every row of the audit's test matrix without
# needing to fake "today" through the HTTP layer.


from app.modules.streak.services.streak_service import _compute_streaks  # noqa: E402


def test_compute_streaks_no_dates() -> None:
    assert _compute_streaks([], TODAY) == (0, 0)


def test_compute_streaks_session_today() -> None:
    assert _compute_streaks([TODAY], TODAY) == (1, 1)


def test_compute_streaks_session_yesterday_only() -> None:
    assert _compute_streaks([YESTERDAY], TODAY) == (1, 1)


def test_compute_streaks_session_two_days_ago_only() -> None:
    assert _compute_streaks([_days_ago(2)], TODAY) == (0, 1)


def test_compute_streaks_consecutive_two_days() -> None:
    assert _compute_streaks([TODAY, YESTERDAY], TODAY) == (2, 2)


def test_compute_streaks_consecutive_seven_days() -> None:
    dates = [_days_ago(i) for i in range(7)]
    assert _compute_streaks(dates, TODAY) == (7, 7)


def test_compute_streaks_gap_breaks_current_but_not_longest() -> None:
    # 3-day streak (days 5,4,3 ago), gap (days 2,1 ago missed), session today.
    dates = [TODAY, _days_ago(3), _days_ago(4), _days_ago(5)]
    assert _compute_streaks(dates, TODAY) == (1, 3)


def test_compute_streaks_requires_distinct_input() -> None:
    """
    `_compute_streaks` documents (in its own docstring) that `dates` must
    already be distinct — de-duplication is the repository's job (`SELECT
    DISTINCT`), proven separately by `test_streak_duplicate_same_day_sessions_count_once`.
    This test just pins that a duplicate entry is *not* silently corrected
    here, so that guarantee is never accidentally assumed to live at this
    layer instead.
    """
    assert _compute_streaks([TODAY, TODAY, YESTERDAY], TODAY) == (1, 2)
