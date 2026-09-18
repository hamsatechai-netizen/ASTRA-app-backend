"""
Blocker A — `users.uid` linking at signup: transaction and repository-level tests.

`test_verify_otp.py` proves the four linking cases through the HTTP path with
in-memory fakes. Those fakes have no transaction semantics, so this module
covers what they cannot:

- the real `UserRepository` flushes the uid assignment (so a dependent insert
  later in the same transaction sees it) and never overwrites a set uid;
- the real `UserRepository.get_by_uid` is a plain UNIQUE-key lookup;
- the real `AthleteProfileRepository` still takes the advisory lock before
  computing `MAX(athlete_id) + 1`, unchanged by this fix;
- `get_db` rolls back on any exception raised inside a request and commits
  otherwise — the mechanism that discards a half-created user/athlete pair
  when a 409 conflict is raised;
- end to end with fakes: the uid linked at signup is exactly what a
  foreign-key-enforcing physiology insert needs, and a returning athlete
  with `uid = NULL` and an unambiguous phone match is now safely
  self-healed the same way (see the "Safe athlete uid self-healing" task) —
  the foreign-key-enforcing physiology insert that used to fail for such an
  account now succeeds after one login.

No real database connection is made anywhere in this file.
"""

import uuid
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from app.dependencies import database as database_module
from app.dependencies.database import get_db
from app.models.athlete_physiology import AthletePhysiology
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.modules.auth.dependencies.services import (
    get_athlete_profile_repository,
    get_otp_repository,
    get_user_repository,
)
from app.modules.auth.exceptions import IdentityConflictException, UidAlreadyAssignedException
from app.modules.auth.repositories.athlete_profile_repository import AthleteProfileRepository
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.baseline.dependencies.services import get_baseline_repository
from app.modules.baseline.repositories.baseline_repository_interface import BaselineRepositoryInterface
from app.modules.onboarding.dependencies.services import get_athlete_details_repository
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

from tests.unit.test_verify_otp import (
    ENDPOINT,
    VALID_OTP,
    VALID_PHONE,
    FakeAthleteDetailsRepository,
    FakeAthleteProfileRepository,
    FakeOTPRepository,
    FakeUserRepository,
)

# --- Minimal SQLAlchemy session stand-in -------------------------------------------------


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar(self) -> Any:
        return self._value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _FakeSession:
    """Records every call the repositories make; returns queued results in order."""

    def __init__(self, results: list[Any] | None = None) -> None:
        self.results = list(results or [])
        self.executed: list[tuple[str, Any]] = []
        self.added: list[Any] = []
        self.flush_count = 0

    async def execute(self, statement: Any, params: Any = None) -> _FakeResult:
        self.executed.append((str(statement), params))
        return _FakeResult(self.results.pop(0) if self.results else None)

    def add(self, instance: Any) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flush_count += 1


# --- UserRepository: assignment is flushed; set uid is never overwritten -----------------


async def test_set_uid_if_absent_sets_uid_and_flushes_immediately() -> None:
    session = _FakeSession()
    user = HamsaTechUser(id=uuid.uuid4(), phone_number=VALID_PHONE)

    await UserRepository(session).set_uid_if_absent(user, "ASA063")  # type: ignore[arg-type]

    assert user.uid == "ASA063"
    assert session.flush_count == 1  # visible to later inserts in the same transaction


async def test_set_uid_if_absent_never_overwrites_and_issues_no_flush_when_already_set() -> None:
    session = _FakeSession()
    user = HamsaTechUser(id=uuid.uuid4(), phone_number=VALID_PHONE, uid="ASA010")

    await UserRepository(session).set_uid_if_absent(user, "ASA063")  # type: ignore[arg-type]

    assert user.uid == "ASA010"
    assert session.flush_count == 0


async def test_get_by_uid_is_a_single_lookup_by_uid() -> None:
    holder = HamsaTechUser(id=uuid.uuid4(), phone_number="+919876500000", uid="ASA063")
    session = _FakeSession(results=[holder])

    found = await UserRepository(session).get_by_uid("ASA063")  # type: ignore[arg-type]

    assert found is holder
    assert len(session.executed) == 1
    assert "users.uid" in session.executed[0][0]


async def test_get_by_uid_returns_none_when_no_account_holds_it() -> None:
    session = _FakeSession(results=[None])

    assert await UserRepository(session).get_by_uid("ASA063") is None  # type: ignore[arg-type]


# --- AthleteProfileRepository: MAX+1 under the advisory lock is untouched ----------------


@pytest.mark.parametrize(("current_max", "expected"), [(62, "ASA063"), (None, "ASA001"), (9, "ASA010")])
async def test_create_minimal_takes_advisory_lock_then_generates_max_plus_one(
    current_max: int | None, expected: str
) -> None:
    session = _FakeSession(results=[None, current_max])  # lock statement, then MAX(...)

    athlete = await AthleteProfileRepository(session).create_minimal(VALID_PHONE)  # type: ignore[arg-type]

    assert athlete.athlete_id == expected
    assert athlete.contact_number == VALID_PHONE
    assert "pg_advisory_xact_lock" in session.executed[0][0]
    assert "MAX(CAST(SUBSTRING(athlete_id FROM 4) AS INTEGER))" in session.executed[1][0]
    assert session.added == [athlete]
    assert session.flush_count == 1


# --- get_db: the rollback that discards a half-created user/athlete on conflict ----------


class _FakeAsyncSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def __aenter__(self) -> "_FakeAsyncSession":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None


@pytest.fixture
def fake_session(monkeypatch: pytest.MonkeyPatch) -> _FakeAsyncSession:
    session = _FakeAsyncSession()
    monkeypatch.setattr(database_module, "AsyncSessionFactory", lambda: session)
    return session


@pytest.mark.parametrize("conflict", [IdentityConflictException(), UidAlreadyAssignedException()])
async def test_get_db_rolls_back_and_does_not_commit_when_a_uid_conflict_is_raised(
    fake_session: _FakeAsyncSession, conflict: Exception
) -> None:
    generator = get_db()
    session = await generator.__anext__()
    assert session is fake_session

    with pytest.raises(type(conflict)):
        await generator.athrow(conflict)

    assert fake_session.rolled_back is True
    assert fake_session.committed is False


async def test_get_db_commits_on_clean_completion(fake_session: _FakeAsyncSession) -> None:
    generator = get_db()
    await generator.__anext__()
    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()

    assert fake_session.committed is True
    assert fake_session.rolled_back is False


# --- End to end with fakes: the linked uid is what the physiology insert needs -----------


class SimulatedForeignKeyViolation(Exception):
    """Stands in for asyncpg's ForeignKeyViolationError on athlete_physiology.athlete_id -> users(uid)."""


class _FkEnforcingBaselineRepository(BaselineRepositoryInterface):
    """Refuses a physiology insert unless some user row holds `athlete_id` as its `uid`."""

    def __init__(self, users: FakeUserRepository, athletes: FakeAthleteProfileRepository) -> None:
        self._users = users
        self._athletes = athletes
        self.rows: list[AthletePhysiology] = []

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self._athletes.athletes.get(phone_number)

    async def create_baseline(
        self, *, athlete_id: str, resting_heart_rate: int, recorded_date: date
    ) -> AthletePhysiology:
        if not any(user.uid == athlete_id for user in self._users.users.values()):
            raise SimulatedForeignKeyViolation(athlete_id)
        row = AthletePhysiology(
            physiology_id=uuid.uuid4(),
            athlete_id=athlete_id,
            resting_heart_rate=resting_heart_rate,
            recorded_date=recorded_date,
            created_at=utc_now().replace(tzinfo=None),
        )
        self.rows.append(row)
        return row

    async def get_latest_baseline(self, athlete_id: str) -> AthletePhysiology | None:
        return self.rows[-1] if self.rows else None


@pytest.fixture
def signup_world(client: TestClient) -> Iterator[dict[str, Any]]:
    users = FakeUserRepository()
    athletes = FakeAthleteProfileRepository()
    otps = FakeOTPRepository()
    baseline = _FkEnforcingBaselineRepository(users, athletes)
    overrides = client.app.dependency_overrides
    overrides[get_otp_repository] = lambda: otps
    overrides[get_user_repository] = lambda: users
    overrides[get_athlete_profile_repository] = lambda: athletes
    overrides[get_athlete_details_repository] = lambda: FakeAthleteDetailsRepository()
    overrides[get_baseline_repository] = lambda: baseline
    try:
        yield {"client": client, "users": users, "athletes": athletes, "otps": otps, "baseline": baseline}
    finally:
        for dependency in (
            get_otp_repository,
            get_user_repository,
            get_athlete_profile_repository,
            get_athlete_details_repository,
            get_baseline_repository,
        ):
            overrides.pop(dependency, None)


def test_uid_linked_at_signup_satisfies_the_physiology_foreign_key(signup_world: dict[str, Any]) -> None:
    client: TestClient = signup_world["client"]
    signup_world["otps"].seed(VALID_PHONE, VALID_OTP)

    verify = client.post(ENDPOINT, json={"phone_number": VALID_PHONE, "otp_code": VALID_OTP})
    assert verify.status_code == 200
    token = verify.json()["access_token"]
    athlete_id = signup_world["athletes"].athletes[VALID_PHONE].athlete_id
    assert signup_world["users"].users[VALID_PHONE].uid == athlete_id

    baseline = client.post(
        f"/api/mobile/athletes/{athlete_id}/baseline",
        json={"resting_hr": 58},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert baseline.status_code == 201
    assert baseline.json()["athlete_id"] == athlete_id
    assert baseline.json()["resting_heart_rate"] == 58


def test_returning_user_with_null_uid_and_unambiguous_phone_is_safely_self_healed(
    signup_world: dict[str, Any],
) -> None:
    """
    Supersedes the old "deliberately not repaired" boundary: a returning
    athlete (profile already exists) whose `uid` is still NULL, with
    exactly one athlete profile on this phone number, now gets it linked
    as a side effect of a normal login — safely, transactionally, and
    without ever touching the athlete row itself. The physiology foreign
    key that used to fail for such an account (the Baseline FK
    investigation) now succeeds on the very next call, no separate repair
    endpoint or manual step required.
    """
    client: TestClient = signup_world["client"]
    existing_user = HamsaTechUser(id=uuid.uuid4(), phone_number=VALID_PHONE)  # uid starts NULL
    signup_world["users"].users[VALID_PHONE] = existing_user
    signup_world["athletes"].athletes[VALID_PHONE] = HamsaTechAthlete(
        athlete_id="ASA057", contact_number=VALID_PHONE, current_onboarding_step=2
    )
    signup_world["otps"].seed(VALID_PHONE, VALID_OTP)

    verify = client.post(ENDPOINT, json={"phone_number": VALID_PHONE, "otp_code": VALID_OTP})
    assert verify.status_code == 200
    assert verify.json()["is_new_user"] is False
    assert verify.json()["next_step"] == "ONBOARDING_STEP_2"
    assert existing_user.uid == "ASA057"  # self-healed by this same login

    baseline = client.post(
        "/api/mobile/athletes/ASA057/baseline",
        json={"resting_hr": 58},
        headers={"Authorization": f"Bearer {verify.json()['access_token']}"},
    )

    assert baseline.status_code == 201
    assert baseline.json()["resting_heart_rate"] == 58


def test_returning_user_uid_self_heal_is_idempotent_across_repeated_logins(
    signup_world: dict[str, Any],
) -> None:
    """A second login for the same phone must not touch the now-set uid or re-log a repair."""
    client: TestClient = signup_world["client"]
    existing_user = HamsaTechUser(id=uuid.uuid4(), phone_number=VALID_PHONE)
    signup_world["users"].users[VALID_PHONE] = existing_user
    signup_world["athletes"].athletes[VALID_PHONE] = HamsaTechAthlete(
        athlete_id="ASA057", contact_number=VALID_PHONE, current_onboarding_step=2
    )

    signup_world["otps"].seed(VALID_PHONE, VALID_OTP)
    first = client.post(ENDPOINT, json={"phone_number": VALID_PHONE, "otp_code": VALID_OTP})
    assert first.status_code == 200 and existing_user.uid == "ASA057"

    signup_world["otps"].seed(VALID_PHONE, VALID_OTP)  # a second, independent successful login
    second = client.post(ENDPOINT, json={"phone_number": VALID_PHONE, "otp_code": VALID_OTP})

    assert second.status_code == 200
    assert existing_user.uid == "ASA057"  # unchanged, not reassigned
    assert len(signup_world["users"].users) == 1
    assert len(signup_world["athletes"].athletes) == 1


def test_returning_user_uid_self_heal_never_overwrites_an_existing_mismatched_uid(
    signup_world: dict[str, Any],
) -> None:
    """
    A returning athlete whose `uid` is already set to something ELSE (a
    pre-existing inconsistency, not the NULL case this feature targets) must
    keep working exactly as before: login succeeds, and the existing uid is
    never touched, matching or not.
    """
    client: TestClient = signup_world["client"]
    existing_user = HamsaTechUser(id=uuid.uuid4(), phone_number=VALID_PHONE, uid="LEGACY-UID-999")
    signup_world["users"].users[VALID_PHONE] = existing_user
    signup_world["athletes"].athletes[VALID_PHONE] = HamsaTechAthlete(
        athlete_id="ASA057", contact_number=VALID_PHONE, current_onboarding_step=2
    )
    signup_world["otps"].seed(VALID_PHONE, VALID_OTP)

    verify = client.post(ENDPOINT, json={"phone_number": VALID_PHONE, "otp_code": VALID_OTP})

    assert verify.status_code == 200
    assert verify.json()["next_step"] == "ONBOARDING_STEP_2"
    assert existing_user.uid == "LEGACY-UID-999"  # never overwritten

    with pytest.raises(SimulatedForeignKeyViolation):
        client.post(
            "/api/mobile/athletes/ASA057/baseline",
            json={"resting_hr": 58},
            headers={"Authorization": f"Bearer {verify.json()['access_token']}"},
        )
