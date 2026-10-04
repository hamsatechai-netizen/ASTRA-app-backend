"""
Comprehensive Verify OTP tests.

Uses fakes for the OTP repository, user repository, athlete-profile
repository, athlete-details repository, and SMS provider (via FastAPI's
`dependency_overrides`) — this never touches the real
`hamsatech.users`/`hamsatech.athletes`/`hamsatech.athlete_details` tables,
which hold real production data. Exercises the full
`router -> AuthService -> (OTPService, UserService, TokenService)` path
with the exact production wiring; only the repository/provider I/O
boundaries are swapped for fakes. The athlete-details repository is faked
because `UserService.resolve_onboarding_status` now reuses
`OnboardingService.is_onboarding_complete` to decide `next_step`.
"""

import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta

import jwt
import pytest
from app.config.settings import get_settings
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_athlete_details import HamsaTechAthleteDetails
from app.models.hamsatech_user import HamsaTechUser
from app.models.otp_challenge import OTPChallenge
from app.modules.auth.constants import JWT_ALGORITHM, OTP_MAX_VERIFICATION_ATTEMPTS
from app.modules.auth.dependencies.services import (
    get_athlete_profile_repository,
    get_otp_repository,
    get_user_repository,
)
from app.modules.auth.exceptions import IdentityConflictException, UidAlreadyAssignedException
from app.modules.auth.repositories.athlete_profile_repository_interface import (
    AthleteContactMatch,
    AthleteProfileRepositoryInterface,
)
from app.modules.auth.repositories.otp_repository_interface import OTPRepositoryInterface
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import hash_otp
from app.modules.onboarding.dependencies.services import get_athlete_details_repository
from app.modules.onboarding.repositories.athlete_details_repository_interface import (
    AthleteDetailsRepositoryInterface,
)
from app.utils.datetime import utc_now
from fastapi.testclient import TestClient

VALID_PHONE = "+919876543210"
VALID_OTP = "123456"
ENDPOINT = "/api/v2/auth/phone/verify-otp"


class FakeOTPRepository(OTPRepositoryInterface):
    def __init__(self) -> None:
        self.records: dict[str, OTPChallenge] = {}

    async def get_by_phone(self, phone_number: str) -> OTPChallenge | None:
        return self.records.get(phone_number)

    async def upsert(self, phone_number: str, otp_hash: str, expires_at: datetime) -> OTPChallenge:
        challenge = OTPChallenge(
            phone_number=phone_number, otp_hash=otp_hash, expires_at=expires_at, attempts=0
        )
        self.records[phone_number] = challenge
        return challenge

    async def increment_attempts(self, phone_number: str) -> int:
        challenge = self.records[phone_number]
        challenge.attempts += 1
        return challenge.attempts

    async def delete_by_phone(self, phone_number: str) -> None:
        self.records.pop(phone_number, None)

    def seed(
        self, phone_number: str, otp_code: str, *, attempts: int = 0, expires_in_seconds: int = 300
    ) -> None:
        self.records[phone_number] = OTPChallenge(
            phone_number=phone_number,
            otp_hash=hash_otp(otp_code),
            expires_at=utc_now() + timedelta(seconds=expires_in_seconds),
            attempts=attempts,
        )


class FakeUserRepository(UserRepositoryInterface):
    def __init__(self) -> None:
        self.users: dict[str, HamsaTechUser] = {}

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        return self.users.get(phone_number)

    async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
        return next((user for user in self.users.values() if user.id == user_id), None)

    async def create(self, phone_number: str) -> HamsaTechUser:
        user = HamsaTechUser(id=uuid.uuid4(), phone_number=phone_number)
        self.users[phone_number] = user
        return user

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        now = utc_now().replace(tzinfo=None)
        user.phone_verified_at = now
        user.last_login_at = now

    async def get_by_uid(self, uid: str) -> HamsaTechUser | None:
        # Mirrors the real repository's UNIQUE-`uid` lookup so Case 4
        # ("candidate uid already held by another account") can be exercised.
        return next((user for user in self.users.values() if user.uid == uid), None)


class FakeAthleteProfileRepository(AthleteProfileRepositoryInterface):
    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}
        self._next_id = 1
        # Phones deliberately modeled as matching MORE than one athlete profile —
        # this dict-keyed-by-phone store can otherwise only ever hold one, so
        # ambiguity has to be simulated explicitly for the returning-athlete
        # uid self-heal tests (the Blocker B duplicate-contact-number class of risk).
        self.duplicate_phone_counts: dict[str, int] = {}

    async def get_by_contact_number(self, phone_number: str) -> AthleteContactMatch:
        # Mirrors the real repository's semantics exactly: a phone flagged via
        # `duplicate_phone_counts` is ambiguous regardless of whatever single
        # entry `self.athletes` might also hold for it — ambiguous and
        # unique-or-none are never both true at once.
        if self.duplicate_phone_counts.get(phone_number, 0) > 1:
            return AthleteContactMatch(athlete=None, is_ambiguous=True)
        return AthleteContactMatch(athlete=self.athletes.get(phone_number), is_ambiguous=False)

    async def create_minimal(self, phone_number: str) -> HamsaTechAthlete:
        athlete = HamsaTechAthlete(athlete_id=f"ASA{self._next_id:03d}", contact_number=phone_number)
        self._next_id += 1
        self.athletes[phone_number] = athlete
        return athlete

    async def count_by_contact_number(self, phone_number: str) -> int:
        if phone_number in self.duplicate_phone_counts:
            return self.duplicate_phone_counts[phone_number]
        return 1 if phone_number in self.athletes else 0


class FakeAthleteDetailsRepository(AthleteDetailsRepositoryInterface):
    def __init__(self) -> None:
        self.details: dict[str, HamsaTechAthleteDetails] = {}  # keyed by athlete_id

    async def get_by_athlete_id(self, athlete_id: str) -> HamsaTechAthleteDetails | None:
        return self.details.get(athlete_id)

    async def create(
        self, athlete_id: str, *, class_: str, school_name: str, academic_performance: str
    ) -> HamsaTechAthleteDetails:
        raise NotImplementedError("Not exercised by verify-otp tests.")

    async def update(
        self,
        details: HamsaTechAthleteDetails,
        *,
        class_: str,
        school_name: str,
        academic_performance: str,
    ) -> HamsaTechAthleteDetails:
        raise NotImplementedError("Not exercised by verify-otp tests.")

    async def create_step_5(
        self,
        athlete_id: str,
        *,
        diet_type: str,
        outside_food_frequency: str,
        sleep_time: str,
        wake_time: str,
    ) -> HamsaTechAthleteDetails:
        raise NotImplementedError("Not exercised by verify-otp tests.")

    async def update_step_5(
        self,
        details: HamsaTechAthleteDetails,
        *,
        diet_type: str,
        outside_food_frequency: str,
        sleep_time: str,
        wake_time: str,
    ) -> HamsaTechAthleteDetails:
        raise NotImplementedError("Not exercised by verify-otp tests.")

    async def create_step_6(
        self,
        athlete_id: str,
        *,
        friend_circle: str,
        anger_pattern: str,
        sadness_pattern: str,
        reason_for_shooting: str,
        athlete_goal: str,
    ) -> HamsaTechAthleteDetails:
        raise NotImplementedError("Not exercised by verify-otp tests.")

    async def update_step_6(
        self,
        details: HamsaTechAthleteDetails,
        *,
        friend_circle: str,
        anger_pattern: str,
        sadness_pattern: str,
        reason_for_shooting: str,
        athlete_goal: str,
    ) -> HamsaTechAthleteDetails:
        raise NotImplementedError("Not exercised by verify-otp tests.")


def _complete_details(athlete_id: str) -> HamsaTechAthleteDetails:
    """An `athlete_details` row with every Step 6 field filled in — the completion signal."""
    return HamsaTechAthleteDetails(
        athlete_id=athlete_id,
        friend_circle="Small, supportive",
        anger_pattern="Rarely, quick to calm down",
        sadness_pattern="Talks it through",
        reason_for_shooting="Self interest",
        athlete_goal="Olympic Gold Medal",
    )


@pytest.fixture
def fake_otp_repository() -> FakeOTPRepository:
    return FakeOTPRepository()


@pytest.fixture
def fake_user_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_athlete_repository() -> FakeAthleteProfileRepository:
    return FakeAthleteProfileRepository()


@pytest.fixture
def fake_athlete_details_repository() -> FakeAthleteDetailsRepository:
    return FakeAthleteDetailsRepository()


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_otp_repository] = lambda: fake_otp_repository
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_athlete_profile_repository] = lambda: fake_athlete_repository
    client.app.dependency_overrides[get_athlete_details_repository] = lambda: fake_athlete_details_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_otp_repository, None)
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_athlete_profile_repository, None)
        client.app.dependency_overrides.pop(get_athlete_details_repository, None)


def _payload(phone: str = VALID_PHONE, otp: str = VALID_OTP) -> dict[str, str]:
    return {"phone_number": phone, "otp_code": otp}


# --- Happy path: new user, no athlete profile -> ONBOARDING_STEP_1 -----------------


def test_verify_otp_new_user_no_athlete_returns_onboarding_step_1(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["is_new_user"] is True
    assert body["next_step"] == "ONBOARDING_STEP_1"
    assert body["token_type"] == "bearer"
    assert "access_token" in body and "refresh_token" in body


def test_verify_otp_creates_athlete_profile_linked_by_phone(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    created = fake_athlete_repository.athletes[VALID_PHONE]
    assert created.contact_number == VALID_PHONE


# --- Happy path: existing athlete, onboarding complete -> HOME ---------------------


def test_verify_otp_existing_athlete_with_completed_onboarding_returns_home(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)
    fake_athlete_repository.athletes[VALID_PHONE] = HamsaTechAthlete(
        athlete_id="ASA999", contact_number=VALID_PHONE, current_onboarding_step=6
    )
    fake_athlete_details_repository.details["ASA999"] = _complete_details("ASA999")

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    assert response.json()["next_step"] == "HOME"


# --- Existing athlete, onboarding incomplete -> resume at saved step ---------------


@pytest.mark.parametrize("saved_step", [1, 2, 3, 4, 5, 6])
def test_verify_otp_existing_athlete_with_incomplete_onboarding_resumes_at_saved_step(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
    saved_step: int,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)
    fake_athlete_repository.athletes[VALID_PHONE] = HamsaTechAthlete(
        athlete_id="ASA999", contact_number=VALID_PHONE, current_onboarding_step=saved_step
    )
    # No athlete_details row at all -> onboarding is not complete regardless of step.

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    assert response.json()["next_step"] == f"ONBOARDING_STEP_{saved_step}"


def test_verify_otp_existing_athlete_with_partial_step_6_details_resumes_at_step_6(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> None:
    """Details row exists but not every Step-6 field is filled in -> still incomplete."""
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)
    fake_athlete_repository.athletes[VALID_PHONE] = HamsaTechAthlete(
        athlete_id="ASA999", contact_number=VALID_PHONE, current_onboarding_step=6
    )
    fake_athlete_details_repository.details["ASA999"] = HamsaTechAthleteDetails(
        athlete_id="ASA999", friend_circle="Small, supportive"
    )

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    assert response.json()["next_step"] == "ONBOARDING_STEP_6"


def test_verify_otp_existing_user_is_new_user_false(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)
    existing_user = HamsaTechUser(id=uuid.uuid4(), phone_number=VALID_PHONE)
    fake_user_repository.users[VALID_PHONE] = existing_user

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["is_new_user"] is False
    assert body["user_id"] == str(existing_user.id)


def test_verify_otp_marks_phone_verified_and_updates_last_login(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    stored_user = fake_user_repository.users[VALID_PHONE]
    assert stored_user.phone_verified_at is not None
    assert stored_user.last_login_at is not None


def test_verify_otp_consumes_the_challenge(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    assert fake_otp_repository.records.get(VALID_PHONE) is None


def test_verify_otp_issues_a_valid_jwt_for_the_user(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    body = response.json()
    settings = get_settings()
    claims = jwt.decode(body["access_token"], settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    assert claims["sub"] == body["user_id"]
    assert claims["type"] == "access"


# --- Failure handling --------------------------------------------------------------


def test_verify_otp_no_challenge_returns_400(wired_client: TestClient) -> None:
    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_OTP"


def test_verify_otp_wrong_code_returns_400_and_increments_attempts(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload(otp="000000"))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_OTP"
    assert fake_otp_repository.records[VALID_PHONE].attempts == 1


def test_verify_otp_expired_returns_400(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP, expires_in_seconds=-10)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OTP_EXPIRED"


def test_verify_otp_too_many_attempts_returns_429(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP, attempts=OTP_MAX_VERIFICATION_ATTEMPTS)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"


def test_verify_otp_failed_verification_never_touches_user_or_athlete(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload(otp="000000"))

    assert response.status_code == 400
    assert fake_user_repository.users == {}
    assert fake_athlete_repository.athletes == {}


# --- Validation ----------------------------------------------------------------


def test_verify_otp_rejects_malformed_otp_code(wired_client: TestClient) -> None:
    response = wired_client.post(ENDPOINT, json=_payload(otp="abc"))
    assert response.status_code == 422


def test_verify_otp_rejects_malformed_phone_number(wired_client: TestClient) -> None:
    response = wired_client.post(ENDPOINT, json=_payload(phone="not-a-phone"))
    assert response.status_code == 422


# --- Swagger / OpenAPI --------------------------------------------------------------


def test_openapi_documents_auth_endpoints_and_schemas(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert "/api/v2/auth/phone/send-otp" in paths
    assert "/api/v2/auth/phone/verify-otp" in paths

    component_schemas = schema["components"]["schemas"]
    assert "SendOTPRequest" in component_schemas
    assert "VerifyOTPRequest" in component_schemas
    assert "AuthResponse" in component_schemas
    assert "OTPSentResponse" in component_schemas


# --- users.uid identity linking (Baseline FK fix) -----------------------------------
#
# Covers the Baseline persistence FK investigation: `hamsatech.athlete_physiology`
# and `hamsatech.polar_credentials` both carry a foreign key from `athlete_id` to
# `hamsatech.users(uid)`, but nothing populated `uid` for accounts created through
# this signup flow. `UserService.resolve_onboarding_status` now links `user.uid` to
# the freshly generated `athlete_id` for a brand-new athlete only, with a
# non-overwrite guard and an explicit conflict safeguard. See that method's
# docstring for the full rationale.


def test_verify_otp_new_signup_sets_user_uid_to_generated_athlete_id(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    created_athlete = fake_athlete_repository.athletes[VALID_PHONE]
    created_user = fake_user_repository.users[VALID_PHONE]
    assert created_user.uid == created_athlete.athlete_id


def test_verify_otp_user_uid_equals_athlete_athlete_id(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    wired_client.post(ENDPOINT, json=_payload())

    created_user = fake_user_repository.users[VALID_PHONE]
    created_athlete = fake_athlete_repository.athletes[VALID_PHONE]
    assert created_user.uid == created_athlete.athlete_id


def test_verify_otp_user_id_remains_uuid_and_is_not_replaced_by_athlete_id(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    created_user = fake_user_repository.users[VALID_PHONE]
    assert isinstance(created_user.id, uuid.UUID)
    assert created_user.id != created_user.uid  # different identifiers, never conflated
    assert response.json()["user_id"] == str(created_user.id)


def test_verify_otp_generated_uid_follows_existing_asa_sequence(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    wired_client.post(ENDPOINT, json=_payload())

    # FakeAthleteProfileRepository mirrors the real advisory-lock MAX+1
    # generator's "ASA{n:03d}" format — unchanged by this fix.
    assert fake_user_repository.users[VALID_PHONE].uid == "ASA001"


def test_verify_otp_returning_user_uid_and_flow_unchanged(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    """A returning athlete (profile already exists) never touches `uid` at all —
    `resolve_onboarding_status`'s new linking code lives strictly inside the
    "no athlete yet" branch, which a returning athlete never enters."""
    user_id = uuid.uuid4()
    fake_user_repository.users[VALID_PHONE] = HamsaTechUser(
        id=user_id, phone_number=VALID_PHONE, uid="ASA999"
    )
    fake_athlete_repository.athletes[VALID_PHONE] = HamsaTechAthlete(
        athlete_id="ASA999", contact_number=VALID_PHONE, current_onboarding_step=3
    )
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    assert response.json()["is_new_user"] is False
    assert response.json()["next_step"] == "ONBOARDING_STEP_3"
    assert fake_user_repository.users[VALID_PHONE].uid == "ASA999"


def test_verify_otp_never_overwrites_existing_matching_uid(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    """A user whose `uid` already equals what the about-to-be-generated athlete_id
    will be: the safeguard's "already consistent" branch — continues safely,
    without error, and without needing to reassign anything."""
    fake_user_repository.users[VALID_PHONE] = HamsaTechUser(
        id=uuid.uuid4(), phone_number=VALID_PHONE, uid="ASA001"
    )
    # No athlete row yet -> the fake's sequence generator will produce "ASA001" next.
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    assert response.json()["next_step"] == "ONBOARDING_STEP_1"
    assert fake_user_repository.users[VALID_PHONE].uid == "ASA001"


def test_verify_otp_conflicting_uid_raises_identity_conflict_and_does_not_overwrite(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    """
    A user whose `uid` is already non-null and disagrees with the athlete_id
    about to be generated: must raise `IdentityConflictException` (409),
    never overwrite the existing `uid`, and never continue onboarding.

    What this fake-based test proves: the exception type/status, and that
    `user.uid` is left exactly as it was. What it CANNOT prove: that the
    newly created `hamsatech.athletes` row is actually rolled back at the
    database level — `FakeAthleteProfileRepository` is a plain in-memory
    dict with no transaction semantics, so it still shows the phantom
    athlete after the exception (asserted below, precisely to make that
    limitation visible rather than hidden). The rollback itself relies on
    `get_db`'s existing `except Exception: await session.rollback()`
    behavior — already-proven, pre-existing machinery this fix reuses
    unchanged, not something new introduced here — and can only be
    verified against a real Postgres transaction, not a fake.
    """
    fake_user_repository.users[VALID_PHONE] = HamsaTechUser(
        id=uuid.uuid4(), phone_number=VALID_PHONE, uid="LEGACY-UID-999"
    )
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDENTITY_CONFLICT"
    assert fake_user_repository.users[VALID_PHONE].uid == "LEGACY-UID-999"
    # Fake-only artifact, not proof of real rollback — see docstring above.
    assert VALID_PHONE in fake_athlete_repository.athletes


def test_verify_otp_athlete_creation_failure_does_not_set_uid(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
) -> None:
    """
    If athlete creation itself fails, `uid` assignment must never be
    reached — it's the line immediately after `create_minimal` succeeds.

    `wired_client.post(...)` raises here rather than returning a response:
    Starlette's `TestClient`/`BaseHTTPMiddleware` re-raises an unhandled
    exception during a request instead of returning the app's real 500
    response — the same pre-existing, project-wide `TestClient` limitation
    already documented in `test_checkin.py`, not specific to this fix.
    """

    class _FailingAthleteProfileRepository(FakeAthleteProfileRepository):
        async def create_minimal(self, phone_number: str) -> HamsaTechAthlete:
            raise RuntimeError("simulated athlete-creation failure")

    wired_client.app.dependency_overrides[get_athlete_profile_repository] = (
        lambda: _FailingAthleteProfileRepository()
    )
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    with pytest.raises(RuntimeError):
        wired_client.post(ENDPOINT, json=_payload())

    # The user row (created by the earlier, independent get_or_create_user
    # step) exists, but never got as far as uid assignment.
    assert fake_user_repository.users[VALID_PHONE].uid is None


def test_verify_otp_repeat_verification_does_not_duplicate_or_reassign_uid(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)
    first = wired_client.post(ENDPOINT, json=_payload())
    assert first.status_code == 200
    first_uid = fake_user_repository.users[VALID_PHONE].uid
    assert first_uid is not None

    # A second, independently successful verification for the same phone
    # (OTP challenges are deleted on success, so a real replay of the same
    # code is already prevented elsewhere — this seeds a fresh one to
    # simulate a second genuine login, not a replay).
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)
    second = wired_client.post(ENDPOINT, json=_payload())

    assert second.status_code == 200
    assert second.json()["is_new_user"] is False
    assert len(fake_athlete_repository.athletes) == 1
    assert fake_user_repository.users[VALID_PHONE].uid == first_uid


def test_identity_conflict_exception_is_a_409_conflict() -> None:
    exc = IdentityConflictException()
    assert exc.status_code == 409
    assert exc.error_code == "IDENTITY_CONFLICT"


# --- Case 4: the generated athlete_id is already another account's uid -------------------
#
# `users.uid` is UNIQUE. Before this safeguard, a brand-new signup whose freshly
# generated `athlete_id` happened to already be some other user's `uid` would
# fail at flush with an IntegrityError — an unhandled 500 (rolled back by
# `get_db`, so no corruption, but no controlled error either). Now it is
# detected before assignment and surfaced as a 409 `UID_ALREADY_ASSIGNED`.

OTHER_PHONE = "+919876500000"


def test_verify_otp_candidate_uid_held_by_another_user_returns_409_and_reassigns_nothing(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    other_user = HamsaTechUser(id=uuid.uuid4(), phone_number=OTHER_PHONE, uid="ASA001")
    fake_user_repository.users[OTHER_PHONE] = other_user
    # No athlete row for VALID_PHONE -> the fake sequence will generate "ASA001" next.
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "UID_ALREADY_ASSIGNED"
    # The other account keeps its mapping; the new account is never linked.
    assert fake_user_repository.users[OTHER_PHONE].uid == "ASA001"
    assert other_user.id == fake_user_repository.users[OTHER_PHONE].id
    assert fake_user_repository.users[VALID_PHONE].uid is None
    # Fake-only artifact (no transaction semantics in the in-memory fake) — the real
    # rollback is `get_db`'s, covered in test_uid_self_healing.py.
    assert VALID_PHONE in fake_athlete_repository.athletes


class _RecordingUserRepository(FakeUserRepository):
    """Records every `set_uid_if_absent` call so a test can prove it was never reached."""

    def __init__(self) -> None:
        super().__init__()
        self.assignment_calls: list[tuple[uuid.UUID, str]] = []

    async def set_uid_if_absent(self, user: HamsaTechUser, uid: str) -> None:
        self.assignment_calls.append((user.id, uid))
        await super().set_uid_if_absent(user, uid)


def test_verify_otp_case_3_conflict_is_detected_before_any_assignment_call(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    """Non-matching existing uid: 409, and `set_uid_if_absent` is never called."""
    recording = _RecordingUserRepository()
    recording.users[VALID_PHONE] = HamsaTechUser(
        id=uuid.uuid4(), phone_number=VALID_PHONE, uid="LEGACY-UID-999"
    )
    wired_client.app.dependency_overrides[get_user_repository] = lambda: recording
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    assert wired_client.post(ENDPOINT, json=_payload()).status_code == 409
    assert recording.assignment_calls == []
    assert recording.users[VALID_PHONE].uid == "LEGACY-UID-999"


def test_verify_otp_case_4_conflict_is_detected_before_any_assignment_call(
    wired_client: TestClient, fake_otp_repository: FakeOTPRepository
) -> None:
    """Candidate uid held by another account: 409, and `set_uid_if_absent` is never called."""
    recording = _RecordingUserRepository()
    recording.users[OTHER_PHONE] = HamsaTechUser(id=uuid.uuid4(), phone_number=OTHER_PHONE, uid="ASA001")
    wired_client.app.dependency_overrides[get_user_repository] = lambda: recording
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)
    # The fixture's athlete fake is fresh: no athlete for VALID_PHONE, so "ASA001" is generated.

    assert wired_client.post(ENDPOINT, json=_payload()).status_code == 409
    assert recording.assignment_calls == []
    assert recording.users[OTHER_PHONE].uid == "ASA001"
    assert recording.users[VALID_PHONE].uid is None


def test_verify_otp_new_signup_links_uid_exactly_once_after_athlete_creation(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    """Happy path ordering: create athlete -> check uid ownership -> assign, once."""
    calls: list[str] = []

    class _OrderedUserRepository(FakeUserRepository):
        async def get_by_uid(self, uid: str) -> HamsaTechUser | None:
            calls.append(f"get_by_uid:{uid}")
            return await super().get_by_uid(uid)

        async def set_uid_if_absent(self, user: HamsaTechUser, uid: str) -> None:
            calls.append(f"set_uid_if_absent:{uid}")
            await super().set_uid_if_absent(user, uid)

    class _OrderedAthleteRepository(FakeAthleteProfileRepository):
        async def create_minimal(self, phone_number: str) -> HamsaTechAthlete:
            athlete = await super().create_minimal(phone_number)
            calls.append(f"create_minimal:{athlete.athlete_id}")
            return athlete

    users = _OrderedUserRepository()
    wired_client.app.dependency_overrides[get_user_repository] = lambda: users
    wired_client.app.dependency_overrides[get_athlete_profile_repository] = (
        lambda: _OrderedAthleteRepository()
    )
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    assert calls == ["create_minimal:ASA001", "get_by_uid:ASA001", "set_uid_if_absent:ASA001"]
    assert users.users[VALID_PHONE].uid == "ASA001"


def test_verify_otp_sequential_id_continues_from_existing_max(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    """The service never computes an id itself: it links whatever the MAX+1 generator returns."""
    fake_athlete_repository.athletes["+910000000001"] = HamsaTechAthlete(
        athlete_id="ASA061", contact_number="+910000000001"
    )
    fake_athlete_repository._next_id = 62  # the fake's stand-in for MAX(athlete_id) + 1
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    assert fake_athlete_repository.athletes[VALID_PHONE].athlete_id == "ASA062"
    assert fake_user_repository.users[VALID_PHONE].uid == "ASA062"


def test_uid_already_assigned_exception_is_a_409_conflict() -> None:
    exc = UidAlreadyAssignedException()
    assert exc.status_code == 409
    assert exc.error_code == "UID_ALREADY_ASSIGNED"


def test_user_repository_interface_get_by_uid_default_reports_no_holder() -> None:
    """The interface's concrete default keeps every unrelated module fake instantiable and
    answers "nobody holds this uid" — the correct answer for fakes that never model uid."""

    class _MinimalFake(UserRepositoryInterface):
        async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
            return None

        async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
            return None

        async def create(self, phone_number: str) -> HamsaTechUser:
            raise NotImplementedError

        async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
            raise NotImplementedError

    import asyncio

    assert asyncio.run(_MinimalFake().get_by_uid("ASA001")) is None


# --- Returning-athlete uid self-heal (Safe Athlete UID Self-Healing task) ----------------
#
# Unlike the four new-signup cases above (which can block signup with a 409 and a
# rollback, since nothing has ever worked for that account yet), self-heal for a
# RETURNING athlete (profile already existed before this login) never raises and
# never blocks login — the account already works; repair is opportunistic. See
# `UserService._attempt_returning_athlete_uid_self_heal` for the full rule set.
# The plain "returning athlete, uid already correct or already set to something
# else" cases are covered by `test_verify_otp_returning_user_uid_and_flow_unchanged`
# and `tests/unit/test_uid_self_healing.py`; this section covers the two NEW
# rejection paths (ambiguous match, uid held by another account) and the
# no-bulk-modification guarantee.


def test_ambiguous_phone_match_is_rejected_at_login_before_anything_runs(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    """Two athlete profiles apparently share this phone number: `get_by_contact_number`
    itself now reports this as ambiguous, so the WHOLE login is rejected with a
    controlled 409 before any athlete-creation or uid decision is made — there is no
    safe way to tell whether this is a new or a returning athlete. Supersedes the old
    "self-heal skipped but login still succeeds" behavior, which relied on a
    `get_by_contact_number` that could not detect its own ambiguity."""
    fake_user_repository.users[VALID_PHONE] = HamsaTechUser(id=uuid.uuid4(), phone_number=VALID_PHONE)
    fake_athlete_repository.athletes[VALID_PHONE] = HamsaTechAthlete(
        athlete_id="ASA057", contact_number=VALID_PHONE, current_onboarding_step=2
    )
    fake_athlete_repository.duplicate_phone_counts[VALID_PHONE] = 2
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AMBIGUOUS_ATHLETE_MATCH"
    assert fake_user_repository.users[VALID_PHONE].uid is None  # never touched
    assert fake_athlete_repository._next_id == 1  # no new athlete was ever created


def test_returning_athlete_self_heal_own_ambiguity_guard_is_defense_in_depth(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
) -> None:
    """Isolates the SECOND, independent ambiguity guard inside self-heal itself
    (`count_by_contact_number`, called fresh at link time) from the top-level guard
    proven above: even if `get_by_contact_number` had already (somehow) resolved a
    single clean match, self-heal must still refuse to link when its OWN re-check
    reports ambiguity. Uses a small local stub rather than the shared fake, since the
    shared fake's `get_by_contact_number` now correctly refuses to produce this
    combination on its own."""

    class _StubAmbiguousAthleteRepository(AthleteProfileRepositoryInterface):
        def __init__(self, athlete: HamsaTechAthlete) -> None:
            self._athlete = athlete

        async def get_by_contact_number(self, phone_number: str) -> AthleteContactMatch:
            return AthleteContactMatch(athlete=self._athlete, is_ambiguous=False)

        async def create_minimal(self, phone_number: str) -> HamsaTechAthlete:
            raise NotImplementedError("Not exercised: only the returning-athlete branch is reached.")

        async def count_by_contact_number(self, phone_number: str) -> int:
            return 2  # ambiguous, independent of get_by_contact_number's own answer

    fake_user_repository.users[VALID_PHONE] = HamsaTechUser(id=uuid.uuid4(), phone_number=VALID_PHONE)
    athlete = HamsaTechAthlete(athlete_id="ASA057", contact_number=VALID_PHONE, current_onboarding_step=2)
    wired_client.app.dependency_overrides[get_athlete_profile_repository] = (
        lambda: _StubAmbiguousAthleteRepository(athlete)
    )
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200  # login itself is unaffected — this guard never blocks it
    assert response.json()["next_step"] == "ONBOARDING_STEP_2"
    assert fake_user_repository.users[VALID_PHONE].uid is None  # not repaired


def test_returning_athlete_uid_held_by_another_account_is_not_reassigned(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    """`ASA057` is already claimed as some OTHER account's uid (a data anomaly,
    not this feature's normal trigger) — self-heal must refuse to reassign it,
    must not touch the other account either, and the returning athlete still
    logs in normally."""
    returning_user = HamsaTechUser(id=uuid.uuid4(), phone_number=VALID_PHONE)
    fake_user_repository.users[VALID_PHONE] = returning_user
    other_user = HamsaTechUser(id=uuid.uuid4(), phone_number=OTHER_PHONE, uid="ASA057")
    fake_user_repository.users[OTHER_PHONE] = other_user
    fake_athlete_repository.athletes[VALID_PHONE] = HamsaTechAthlete(
        athlete_id="ASA057", contact_number=VALID_PHONE, current_onboarding_step=2
    )
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    assert response.json()["next_step"] == "ONBOARDING_STEP_2"
    assert returning_user.uid is None  # never reassigned to this account
    assert other_user.uid == "ASA057"  # the other account's mapping is untouched


def test_returning_athlete_self_heal_never_bulk_modifies_other_null_uid_accounts(
    wired_client: TestClient,
    fake_otp_repository: FakeOTPRepository,
    fake_user_repository: FakeUserRepository,
    fake_athlete_repository: FakeAthleteProfileRepository,
) -> None:
    """Several returning athletes all have `uid IS NULL` (the six legacy accounts
    this task is scoped around) — logging in as ONE of them must self-heal only
    that one account, never the others, proving the repair is scoped per-user."""
    phones = [VALID_PHONE, OTHER_PHONE, "+919876500001"]
    athlete_ids = ["ASA057", "ASA058", "ASA059"]
    for phone, athlete_id in zip(phones, athlete_ids, strict=True):
        fake_user_repository.users[phone] = HamsaTechUser(id=uuid.uuid4(), phone_number=phone)
        fake_athlete_repository.athletes[phone] = HamsaTechAthlete(
            athlete_id=athlete_id, contact_number=phone, current_onboarding_step=2
        )
    fake_otp_repository.seed(VALID_PHONE, VALID_OTP)

    response = wired_client.post(ENDPOINT, json=_payload())

    assert response.status_code == 200
    assert fake_user_repository.users[VALID_PHONE].uid == "ASA057"  # only this one healed
    assert fake_user_repository.users[OTHER_PHONE].uid is None
    assert fake_user_repository.users["+919876500001"].uid is None


def test_athlete_profile_repository_interface_count_by_contact_number_default_assumes_unambiguous() -> None:
    """The interface's concrete default answers "exactly one" — correct for any fake
    that (like the base ABC itself) has no way to model more than one athlete per
    phone number, matching the same precedent as `UserRepositoryInterface`'s defaults."""

    class _MinimalFake(AthleteProfileRepositoryInterface):
        async def get_by_contact_number(self, phone_number: str) -> AthleteContactMatch:
            return AthleteContactMatch(athlete=None, is_ambiguous=False)

        async def create_minimal(self, phone_number: str) -> HamsaTechAthlete:
            raise NotImplementedError

    import asyncio

    assert asyncio.run(_MinimalFake().count_by_contact_number(VALID_PHONE)) == 1


def test_user_repository_interface_try_self_heal_uid_default_composes_existing_guards() -> None:
    """The interface's concrete default reuses `get_by_uid` + `set_uid_if_absent` rather
    than duplicating their logic — proven directly against the base ABC's own (permissive)
    defaults: with nothing else known, an absent uid gets linked."""

    class _MinimalFake(UserRepositoryInterface):
        async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
            return None

        async def get_by_id(self, user_id: uuid.UUID) -> HamsaTechUser | None:
            return None

        async def create(self, phone_number: str) -> HamsaTechUser:
            raise NotImplementedError

        async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
            raise NotImplementedError

    import asyncio

    user = HamsaTechUser(id=uuid.uuid4(), phone_number=VALID_PHONE)
    healed = asyncio.run(_MinimalFake().try_self_heal_uid(user, "ASA057"))

    assert healed is True
    assert user.uid == "ASA057"
