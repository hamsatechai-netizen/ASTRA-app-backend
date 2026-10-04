"""
Real-PostgreSQL regression tests for returning-athlete `users.uid` self-healing,
including `AthleteProfileRepository.get_by_contact_number`'s own fix (it used to
raise `MultipleResultsFound` — an unhandled 500 for the whole login request — the
moment two `hamsatech.athletes` rows shared a `contact_number`; no unique
constraint exists on that column).

`tests/unit/test_verify_otp.py` and `tests/unit/test_uid_self_healing.py` prove
the branching logic with in-memory fakes; those fakes have no real transaction
or uniqueness-constraint semantics. This module proves what only a real
Postgres can: a genuine duplicate-`contact_number` pair going through the full
`verify-otp` HTTP path returns a controlled 409 (not a crash) and leaves every
row untouched, including the request-scoped rollback of the `users` row
`get_or_create_user` may have just created earlier in the SAME request; the
atomic conditional UPDATE actually enforces uniqueness under concurrency; and
the `users_uid_key` / `athletes_pkey` constraints are exactly what the
self-heal guard relies on.

Same safety gate as `test_otp_lockout_postgres.py`: runs ONLY when
`ASTRA_INTEGRATION_DB_URL` is set, points at a *local* database (127.0.0.1 /
localhost), and equals `DATABASE_URL` — otherwise the whole module is skipped.
Every row this module creates is phone-scoped synthetic data, deleted again by
each fixture's teardown; no existing row (including ASA001/ASA002-style
production data, which does not exist in this local database at all) is ever
touched.

    DATABASE_URL=postgresql+asyncpg://astra_smoke@127.0.0.1:55432/astra_smoke \\
    ASTRA_INTEGRATION_DB_URL=$DATABASE_URL DATABASE_SSL_REQUIRED=false \\
    pytest tests/integration/test_uid_self_heal_postgres.py
"""

import asyncio
import os
import re
import secrets
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

import asyncpg
import pytest
from app.config.settings import get_settings
from app.database.session import build_connect_args
from app.modules.auth.dependencies.services import get_sms_provider
from app.modules.auth.providers.sms_provider import SMSProviderInterface
from app.modules.auth.repositories.athlete_profile_repository_interface import (
    AthleteContactMatch,
    AthleteProfileRepositoryInterface,
)
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.services.user_service import UserService
from app.modules.onboarding.repositories.athlete_details_repository import AthleteDetailsRepository
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

INTEGRATION_URL = os.environ.get("ASTRA_INTEGRATION_DB_URL", "")
_LOCAL_URL = re.compile(r"^postgresql\+asyncpg://[^@/]+@(127\.0\.0\.1|localhost):\d+/\w+$")

pytestmark = pytest.mark.skipif(
    not _LOCAL_URL.match(INTEGRATION_URL) or os.environ.get("DATABASE_URL") != INTEGRATION_URL,
    reason="requires ASTRA_INTEGRATION_DB_URL pointing at a LOCAL database and equal to DATABASE_URL",
)

SEND = "/api/v2/auth/phone/send-otp"
VERIFY = "/api/v2/auth/phone/verify-otp"


def _db_args() -> dict[str, Any]:
    parts = urlsplit(INTEGRATION_URL.replace("postgresql+asyncpg://", "postgresql://"))
    return {
        "host": parts.hostname,
        "port": parts.port,
        "user": parts.username,
        "password": parts.password,
        "database": parts.path.lstrip("/"),
    }


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(**_db_args())


def db_val(query: str, *args: Any) -> Any:
    """Run one read on the LOCAL integration database over a raw asyncpg connection."""

    async def _run() -> Any:
        connection = await _connect()
        try:
            return await connection.fetchval(query, *args)
        finally:
            await connection.close()

    return asyncio.run(_run())


def db_exec(query: str, *args: Any) -> None:
    async def _run() -> None:
        connection = await _connect()
        try:
            await connection.execute(query, *args)
        finally:
            await connection.close()

    asyncio.run(_run())


@asynccontextmanager
async def _isolated_session() -> AsyncIterator[AsyncSession]:
    """
    A throwaway, `NullPool`-backed SQLAlchemy session bound to the same local
    database, created and fully disposed within one call.

    Deliberately NOT the app's own module-level `engine`/`AsyncSessionFactory`:
    those pool real asyncpg connections, which are bound to the event loop
    that created them. This file drives async code from plain (sync) test
    functions via repeated `asyncio.run()` calls, each of which opens and
    closes its own event loop — reusing a pooled connection across two such
    loops fails with "Future attached to a different loop" /
    "Event loop is closed" the moment the pool later tries to use or close
    it. A private engine created and disposed inside the SAME `asyncio.run()`
    call sidesteps this entirely: nothing outlives the loop that created it.
    """
    settings = get_settings()
    engine = create_async_engine(
        str(settings.DATABASE_URL), poolclass=NullPool, connect_args=build_connect_args(settings)
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, autoflush=False, autocommit=False, expire_on_commit=False
    )
    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()


def seed_athlete(athlete_id: str, phone: str, *, step: int = 2) -> None:
    db_exec(
        "INSERT INTO hamsatech.athletes (athlete_id, contact_number, current_onboarding_step) "
        "VALUES ($1, $2, $3)",
        athlete_id,
        phone,
        step,
    )


def seed_user(phone: str, *, uid: str | None = None) -> uuid.UUID:
    user_id = uuid.uuid4()
    db_exec(
        "INSERT INTO hamsatech.users (id, phone_number, uid, phone_verified_at) "
        "VALUES ($1, $2, $3, now())",
        user_id,
        phone,
        uid,
    )
    return user_id


def uid_of_phone(phone: str) -> str | None:
    return db_val("SELECT uid FROM hamsatech.users WHERE phone_number = $1", phone)


def athlete_snapshot(athlete_id: str) -> tuple[Any, ...]:
    """Every column of one athlete row — used to prove self-heal never writes to `athletes`."""
    return db_val("SELECT (a.*)::text FROM hamsatech.athletes a WHERE athlete_id = $1", athlete_id)


class CapturingSMSProvider(SMSProviderInterface):
    def __init__(self, store: dict[str, str]) -> None:
        self._store = store

    async def send(self, phone_number: str, message: str) -> None:
        match = re.search(r"\b(\d{6})\b", message)
        self._store[phone_number] = match.group(1) if match else ""


@pytest.fixture(scope="module", autouse=True)
def _engine_is_local() -> None:
    from app.database.session import engine

    assert engine.url.host in ("127.0.0.1", "localhost") and engine.url.database == _db_args()["database"]


@pytest.fixture
def phones() -> Iterator[list[str]]:
    """Up to five synthetic phone numbers for one test; all rows they touch are deleted after."""
    numbers = [f"+91999992{secrets.randbelow(10_000):04d}{i}" for i in range(5)]
    yield numbers
    for number in numbers:
        db_exec(
            "DELETE FROM hamsatech.athlete_physiology WHERE athlete_id IN "
            "(SELECT athlete_id FROM hamsatech.athletes WHERE contact_number = $1)",
            number,
        )
        db_exec("DELETE FROM hamsatech.athletes WHERE contact_number = $1", number)
        db_exec("DELETE FROM hamsatech.users WHERE phone_number = $1", number)
        db_exec("DELETE FROM public.otp_challenges WHERE phone_number = $1", number)


@pytest.fixture
def otp_client(client: TestClient) -> Iterator[tuple[TestClient, dict[str, str]]]:
    codes: dict[str, str] = {}
    client.app.dependency_overrides[get_sms_provider] = lambda: CapturingSMSProvider(codes)
    try:
        yield client, codes
    finally:
        client.app.dependency_overrides.pop(get_sms_provider, None)


def _send(client: TestClient, phone: str) -> None:
    assert client.post(SEND, json={"phone": phone}).status_code == 200


def _verify(client: TestClient, phone: str, code: str) -> Any:
    return client.post(VERIFY, json={"phone_number": phone, "otp_code": code})


# --- End-to-end through the real HTTP path (real UserRepository, real AthleteProfileRepository) ---


def test_valid_uid_remains_unchanged_on_ordinary_returning_login(
    otp_client: tuple[TestClient, dict[str, str]], phones: list[str]
) -> None:
    client, codes = otp_client
    phone = phones[0]
    seed_athlete("ASA9001", phone)
    seed_user(phone, uid="ASA9001")
    before = athlete_snapshot("ASA9001")
    _send(client, phone)

    response = _verify(client, phone, codes[phone])

    assert response.status_code == 200
    assert response.json()["next_step"] == "ONBOARDING_STEP_2"
    assert uid_of_phone(phone) == "ASA9001"  # untouched
    assert athlete_snapshot("ASA9001") == before  # athlete row untouched


def test_missing_uid_is_linked_when_the_match_is_unambiguous(
    otp_client: tuple[TestClient, dict[str, str]], phones: list[str]
) -> None:
    client, codes = otp_client
    phone = phones[0]
    seed_athlete("ASA9002", phone)
    seed_user(phone)  # uid NULL
    _send(client, phone)

    response = _verify(client, phone, codes[phone])

    assert response.status_code == 200
    assert response.json()["is_new_user"] is False
    assert response.json()["next_step"] == "ONBOARDING_STEP_2"
    assert uid_of_phone(phone) == "ASA9002"


def test_self_heal_is_idempotent_across_repeated_real_logins(
    otp_client: tuple[TestClient, dict[str, str]], phones: list[str]
) -> None:
    client, codes = otp_client
    phone = phones[0]
    seed_athlete("ASA9003", phone)
    seed_user(phone)
    _send(client, phone)
    first = _verify(client, phone, codes[phone])
    assert first.status_code == 200
    assert uid_of_phone(phone) == "ASA9003"

    for _ in range(3):
        db_exec(
            "UPDATE public.otp_challenges SET updated_at = now() - interval '1 hour' "
            "WHERE phone_number = $1",
            phone,
        )
        _send(client, phone)
        repeat = _verify(client, phone, codes[phone])
        assert repeat.status_code == 200
        assert repeat.json()["is_new_user"] is False

    assert uid_of_phone(phone) == "ASA9003"  # never duplicated, never reassigned
    assert db_val("SELECT count(*) FROM hamsatech.users WHERE phone_number = $1", phone) == 1
    assert db_val("SELECT count(*) FROM hamsatech.athletes WHERE contact_number = $1", phone) == 1


def test_existing_mismatched_uid_is_never_overwritten(
    otp_client: tuple[TestClient, dict[str, str]], phones: list[str]
) -> None:
    client, codes = otp_client
    phone = phones[0]
    seed_athlete("ASA9004", phone)
    seed_user(phone, uid="LEGACY-VALUE-XYZ")
    _send(client, phone)

    response = _verify(client, phone, codes[phone])

    assert response.status_code == 200  # login still works
    assert response.json()["next_step"] == "ONBOARDING_STEP_2"
    assert uid_of_phone(phone) == "LEGACY-VALUE-XYZ"  # never overwritten


def test_cannot_link_to_another_athletes_uid(
    otp_client: tuple[TestClient, dict[str, str]], phones: list[str]
) -> None:
    client, codes = otp_client
    phone, other_phone = phones[0], phones[1]
    seed_athlete("ASA9005", phone)
    seed_user(phone)  # uid NULL — this is the account that should be healed
    seed_user(other_phone, uid="ASA9005")  # a DIFFERENT account already claims it
    _send(client, phone)

    response = _verify(client, phone, codes[phone])

    assert response.status_code == 200  # login for the rightful phone still works
    assert response.json()["next_step"] == "ONBOARDING_STEP_2"
    assert uid_of_phone(phone) is None  # never linked
    assert uid_of_phone(other_phone) == "ASA9005"  # the other account is untouched


def test_duplicate_contact_number_at_login_is_rejected_without_any_mutation(
    otp_client: tuple[TestClient, dict[str, str]], phones: list[str]
) -> None:
    """The exact failure being fixed: two REAL athlete rows sharing one contact_number used
    to make `get_by_contact_number`'s `scalar_one_or_none()` raise `MultipleResultsFound`,
    crashing the whole verify-otp request as an unhandled 500. It must now return a
    controlled 409, and — provable only against a real database, not a fake — the WHOLE
    request must roll back completely: no `users` row survives for this phone, even though
    `get_or_create_user` runs (and would normally persist a row) earlier in the same
    request, before the ambiguity is ever detected."""
    client, codes = otp_client
    phone = phones[0]
    seed_athlete("ASA9020", phone)
    seed_athlete("ASA9021", phone)  # same contact_number: a genuine duplicate
    before_athletes = db_val("SELECT count(*) FROM hamsatech.athletes WHERE contact_number = $1", phone)
    _send(client, phone)

    response = _verify(client, phone, codes[phone])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AMBIGUOUS_ATHLETE_MATCH"
    # the whole request rolled back: no users row survives for this phone
    assert db_val("SELECT count(*) FROM hamsatech.users WHERE phone_number = $1", phone) == 0
    # neither athlete row was touched, and no third was created
    assert (
        db_val("SELECT count(*) FROM hamsatech.athletes WHERE contact_number = $1", phone) == before_athletes
    )


def test_legacy_null_uid_accounts_are_not_bulk_modified(
    otp_client: tuple[TestClient, dict[str, str]], phones: list[str]
) -> None:
    """Three separate returning athletes, all NULL uid (the six-legacy-account shape) —
    logging in as only one must heal only that one."""
    client, codes = otp_client
    logging_in_phone = phones[0]
    for athlete_id, phone in [("ASA9006", phones[0]), ("ASA9007", phones[1]), ("ASA9008", phones[2])]:
        seed_athlete(athlete_id, phone)
        seed_user(phone)
    _send(client, logging_in_phone)

    response = _verify(client, logging_in_phone, codes[logging_in_phone])

    assert response.status_code == 200
    assert uid_of_phone(phones[0]) == "ASA9006"  # healed
    assert uid_of_phone(phones[1]) is None  # untouched
    assert uid_of_phone(phones[2]) is None  # untouched


# --- count_by_contact_number against genuine duplicate rows ------------------------------


def test_count_by_contact_number_detects_real_duplicate_athletes(phones: list[str]) -> None:
    """A genuine `hamsatech.athletes` duplicate-contact-number pair (the Blocker B class of
    risk) — proves the new count query itself, against real duplicated data, never raises
    and reports the true count (unlike `get_by_contact_number`'s `scalar_one_or_none()`)."""
    from app.modules.auth.repositories.athlete_profile_repository import AthleteProfileRepository

    phone = phones[0]
    seed_athlete("ASA9010", phone)
    seed_athlete("ASA9011", phone)  # same contact_number, a second athlete row

    async def _count() -> int:
        async with _isolated_session() as session:
            return await AthleteProfileRepository(session).count_by_contact_number(phone)

    assert asyncio.run(_count()) == 2


class _StubAmbiguousAthleteRepository(AthleteProfileRepositoryInterface):
    """Simulates `get_by_contact_number` having already (somehow) resolved a single, clean
    match while `count_by_contact_number` independently reports ambiguity — isolates
    self-heal's OWN defense-in-depth guard (see `UserService
    ._attempt_returning_athlete_uid_self_heal`'s docstring) from the top-level guard, which
    `test_duplicate_contact_number_at_login_is_rejected_without_any_mutation` above already
    proves against genuinely duplicated real rows."""

    def __init__(self, athlete: Any, ambiguous_count: int) -> None:
        self._athlete = athlete
        self._ambiguous_count = ambiguous_count

    async def get_by_contact_number(self, phone_number: str) -> AthleteContactMatch:
        return AthleteContactMatch(athlete=self._athlete, is_ambiguous=False)

    async def create_minimal(self, phone_number: str) -> Any:
        raise NotImplementedError("Not exercised: this test only reaches the returning-athlete branch.")

    async def count_by_contact_number(self, phone_number: str) -> int:
        return self._ambiguous_count


def test_self_heal_own_ambiguity_guard_leaves_the_real_database_unchanged(phones: list[str]) -> None:
    """With a real Postgres-backed `UserRepository`, self-heal's own ambiguity signal must
    result in zero writes to `hamsatech.users` — proven by asserting the real row is
    untouched after the service call, not just by a fake's in-memory state."""
    from app.models.hamsatech_athlete import HamsaTechAthlete

    phone = phones[0]
    seed_athlete("ASA9012", phone)
    seed_user(phone)

    async def _run() -> None:
        async with _isolated_session() as session:
            athlete = HamsaTechAthlete(athlete_id="ASA9012", contact_number=phone, current_onboarding_step=2)
            service = UserService(
                UserRepository(session),
                _StubAmbiguousAthleteRepository(athlete, ambiguous_count=2),
                AthleteDetailsRepository(session),
            )
            user = await UserRepository(session).get_by_phone(phone)
            assert user is not None
            status = await service.resolve_onboarding_status(phone, user)
            assert str(status) == "ONBOARDING_STEP_2" or status.value == "ONBOARDING_STEP_2"
            await session.commit()

    asyncio.run(_run())

    assert uid_of_phone(phone) is None  # never linked


# --- Genuine concurrency: two different accounts racing for the same candidate uid -------


def test_concurrent_self_heal_for_the_same_candidate_uid_only_one_wins(phones: list[str]) -> None:
    """Two DIFFERENT user rows simultaneously attempt to claim the SAME candidate uid, each
    on its own real connection/transaction — proves the atomic UPDATE's WHERE-clause guard
    plus the SAVEPOINT/IntegrityError fallback actually serialize correctly under real
    concurrent Postgres transactions: exactly one link succeeds, the loser cleanly returns
    False (no unhandled exception), and the database ends up consistent."""
    phone_a, phone_b = phones[0], phones[1]
    user_a_id = seed_user(phone_a)
    user_b_id = seed_user(phone_b)
    candidate_uid = "ASA9099"  # no athlete row required: try_self_heal_uid only touches users

    async def _attempt(user_id: uuid.UUID) -> bool:
        async with _isolated_session() as session:
            repository = UserRepository(session)
            user = await repository.get_by_id(user_id)
            assert user is not None
            healed = await repository.try_self_heal_uid(user, candidate_uid)
            await session.commit()
            return healed

    async def _race() -> list[bool]:
        return await asyncio.gather(_attempt(user_a_id), _attempt(user_b_id))

    results = asyncio.run(_race())

    assert sorted(results) == [False, True]  # exactly one won
    winners = [phone for phone in (phone_a, phone_b) if uid_of_phone(phone) == candidate_uid]
    assert len(winners) == 1  # the database agrees with exactly one winner
    loser_phone = phone_b if winners == [phone_a] else phone_a
    assert uid_of_phone(loser_phone) is None  # the loser was never linked to anything
