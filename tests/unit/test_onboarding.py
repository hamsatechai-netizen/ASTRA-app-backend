"""
Comprehensive onboarding Steps 1-6 tests.

Uses fakes for the user, onboarding, and athlete-details repositories
(via FastAPI's `dependency_overrides`) instead of a real Postgres/Supabase
connection — this sandboxed test environment has neither. Requests carry
a real JWT access token (via `create_access_token`), so
`get_current_athlete`'s actual decode-and-lookup logic is exercised
end-to-end, not stubbed out.
"""

import uuid
from collections.abc import Iterator
from datetime import date
from uuid import UUID

import pytest
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_athlete_details import HamsaTechAthleteDetails
from app.models.hamsatech_user import HamsaTechUser
from app.modules.auth.dependencies.services import get_user_repository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.security import create_access_token, create_refresh_token
from app.modules.onboarding.dependencies.services import (
    get_athlete_details_repository,
    get_onboarding_repository,
)
from app.modules.onboarding.repositories.athlete_details_repository_interface import (
    AthleteDetailsRepositoryInterface,
)
from app.modules.onboarding.repositories.onboarding_repository_interface import (
    OnboardingRepositoryInterface,
)
from fastapi.testclient import TestClient

STATUS_ENDPOINT = "/api/v2/onboarding"
STEP_1_ENDPOINT = "/api/v2/onboarding/step-1"
STEP_2_ENDPOINT = "/api/v2/onboarding/step-2"
STEP_3_ENDPOINT = "/api/v2/onboarding/step-3"
STEP_4_ENDPOINT = "/api/v2/onboarding/step-4"
STEP_5_ENDPOINT = "/api/v2/onboarding/step-5"
STEP_6_ENDPOINT = "/api/v2/onboarding/step-6"
PHONE_NUMBER = "+919876543210"
ATHLETE_ID = "ASA001"
ACADEMY_ID = "11111111-1111-1111-1111-111111111111"

VALID_STEP_1_BODY = {
    "fullName": "Jane Doe",
    "dateOfBirth": "2005-04-12",
    "gender": "Female",
    "city": "Mumbai",
}

VALID_STEP_2_BODY = {
    "discipline": "10m Air Rifle",
    "experienceLevel": "1 - 2 Years (Intermediate)",
    "yearsShooting": 2,
    "academyId": ACADEMY_ID,
}

VALID_STEP_3_BODY = {
    "averagePracticeScore": 72.5,
    "targetScore": 95.0,
    "performanceBlockers": ["Anxiety", "Inconsistent breathing"],
    "goal30Day": "Improve stance stability",
    "goal6Month": "Qualify for nationals",
}

VALID_STEP_4_BODY = {
    "class": "9th",
    "schoolName": "Sri Prakash",
    "academicPerformance": "80-90%",
}

VALID_STEP_5_BODY = {
    "dietType": "Mix",
    "outsideFoodFrequency": "Weekly",
    "sleepTime": "7hrs",
    "wakeTime": "5:30 AM",
}

VALID_STEP_6_BODY = {
    "friendCircle": "Small, supportive",
    "angerPattern": "Rarely, quick to calm down",
    "sadnessPattern": "Talks it through",
    "reasonForShooting": "Parents' encouragement, self interest",
    "athleteGoal": "Olympic Gold Medal",
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
        raise NotImplementedError("Not exercised by onboarding tests.")

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        raise NotImplementedError("Not exercised by onboarding tests.")


class FakeOnboardingRepository(OnboardingRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed onboarding repository."""

    def __init__(self) -> None:
        self.athletes: dict[str, HamsaTechAthlete] = {}  # keyed by contact_number

    async def get_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        return self.athletes.get(phone_number)

    async def save_step_1(
        self,
        athlete: HamsaTechAthlete,
        *,
        full_name: str,
        date_of_birth: date,
        gender: str,
        city: str,
    ) -> HamsaTechAthlete:
        athlete.athlete_name = full_name
        athlete.date_of_birth = date_of_birth
        athlete.gender = gender
        athlete.city = city
        athlete.current_onboarding_step = 2
        return athlete

    async def save_step_2(
        self,
        athlete: HamsaTechAthlete,
        *,
        discipline: str,
        experience_level: str,
        years_shooting: int,
        academy_id: UUID,
    ) -> HamsaTechAthlete:
        athlete.weapon_specialization = discipline
        athlete.experience_level = experience_level
        athlete.years_shooting = years_shooting
        athlete.academy_id = academy_id
        athlete.current_onboarding_step = 3
        return athlete

    async def save_step_3(
        self,
        athlete: HamsaTechAthlete,
        *,
        average_practice_score: float,
        target_score: float,
        performance_blockers: list[str],
        goal_30_day: str,
        goal_6_month: str,
    ) -> HamsaTechAthlete:
        athlete.avg_practice_score = average_practice_score
        athlete.target_score = target_score
        athlete.performance_blockers = performance_blockers
        athlete.goal_30_day = goal_30_day
        athlete.goal_6_month = goal_6_month
        athlete.current_onboarding_step = 4
        return athlete

    async def advance_onboarding_step(self, athlete: HamsaTechAthlete, step: int) -> HamsaTechAthlete:
        athlete.current_onboarding_step = step
        return athlete


class FakeAthleteDetailsRepository(AthleteDetailsRepositoryInterface):
    """In-memory stand-in for the SQLAlchemy-backed athlete-details repository."""

    def __init__(self) -> None:
        self.details: dict[str, HamsaTechAthleteDetails] = {}  # keyed by athlete_id

    async def get_by_athlete_id(self, athlete_id: str) -> HamsaTechAthleteDetails | None:
        return self.details.get(athlete_id)

    async def create(
        self, athlete_id: str, *, class_: str, school_name: str, academic_performance: str
    ) -> HamsaTechAthleteDetails:
        details = HamsaTechAthleteDetails(
            athlete_id=athlete_id,
            class_=class_,
            school_name=school_name,
            academic_performance=academic_performance,
        )
        self.details[athlete_id] = details
        return details

    async def update(
        self,
        details: HamsaTechAthleteDetails,
        *,
        class_: str,
        school_name: str,
        academic_performance: str,
    ) -> HamsaTechAthleteDetails:
        details.class_ = class_
        details.school_name = school_name
        details.academic_performance = academic_performance
        return details

    async def create_step_5(
        self,
        athlete_id: str,
        *,
        diet_type: str,
        outside_food_frequency: str,
        sleep_time: str,
        wake_time: str,
    ) -> HamsaTechAthleteDetails:
        details = HamsaTechAthleteDetails(
            athlete_id=athlete_id,
            diet_type=diet_type,
            outside_food_frequency=outside_food_frequency,
            sleep_time=sleep_time,
            wake_time=wake_time,
        )
        self.details[athlete_id] = details
        return details

    async def update_step_5(
        self,
        details: HamsaTechAthleteDetails,
        *,
        diet_type: str,
        outside_food_frequency: str,
        sleep_time: str,
        wake_time: str,
    ) -> HamsaTechAthleteDetails:
        details.diet_type = diet_type
        details.outside_food_frequency = outside_food_frequency
        details.sleep_time = sleep_time
        details.wake_time = wake_time
        return details

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
        details = HamsaTechAthleteDetails(
            athlete_id=athlete_id,
            friend_circle=friend_circle,
            anger_pattern=anger_pattern,
            sadness_pattern=sadness_pattern,
            reason_for_shooting=reason_for_shooting,
            athlete_goal=athlete_goal,
        )
        self.details[athlete_id] = details
        return details

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
        details.friend_circle = friend_circle
        details.anger_pattern = anger_pattern
        details.sadness_pattern = sadness_pattern
        details.reason_for_shooting = reason_for_shooting
        details.athlete_goal = athlete_goal
        return details


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_user_repository(user_id: uuid.UUID) -> FakeUserRepository:
    repository = FakeUserRepository()
    repository.users[user_id] = HamsaTechUser(id=user_id, phone_number=PHONE_NUMBER)
    return repository


@pytest.fixture
def fake_onboarding_repository() -> FakeOnboardingRepository:
    return FakeOnboardingRepository()


@pytest.fixture
def fake_athlete_details_repository() -> FakeAthleteDetailsRepository:
    return FakeAthleteDetailsRepository()


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wired_client(
    client: TestClient,
    fake_user_repository: FakeUserRepository,
    fake_onboarding_repository: FakeOnboardingRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> Iterator[TestClient]:
    client.app.dependency_overrides[get_user_repository] = lambda: fake_user_repository
    client.app.dependency_overrides[get_onboarding_repository] = lambda: fake_onboarding_repository
    client.app.dependency_overrides[get_athlete_details_repository] = lambda: fake_athlete_details_repository
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_user_repository, None)
        client.app.dependency_overrides.pop(get_onboarding_repository, None)
        client.app.dependency_overrides.pop(get_athlete_details_repository, None)


def _existing_athlete(current_onboarding_step: int = 1) -> HamsaTechAthlete:
    return HamsaTechAthlete(
        athlete_id=ATHLETE_ID,
        contact_number=PHONE_NUMBER,
        current_onboarding_step=current_onboarding_step,
    )


# --- Authentication ------------------------------------------------------------


def test_get_onboarding_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.get(STATUS_ENDPOINT)
    assert response.status_code == 401


def test_get_onboarding_rejects_invalid_token(wired_client: TestClient) -> None:
    response = wired_client.get(STATUS_ENDPOINT, headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_get_onboarding_rejects_refresh_token_used_as_access_token(
    wired_client: TestClient, user_id: uuid.UUID
) -> None:
    refresh_token = create_refresh_token(user_id)
    response = wired_client.get(STATUS_ENDPOINT, headers={"Authorization": f"Bearer {refresh_token}"})
    assert response.status_code == 401


def test_get_onboarding_rejects_unknown_user(wired_client: TestClient) -> None:
    token = create_access_token(uuid.uuid4())  # a user_id no fake repository knows about
    response = wired_client.get(STATUS_ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# --- GET /api/v2/onboarding ------------------------------------------------------


def test_get_onboarding_athlete_not_found(wired_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired_client.get(STATUS_ENDPOINT, headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


def test_get_onboarding_not_started_returns_step_1(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=1)

    response = wired_client.get(STATUS_ENDPOINT, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["athlete_id"] == ATHLETE_ID
    assert body["current_onboarding_step"] == 1
    assert body["is_onboarding_complete"] is False
    assert body["full_name"] is None
    assert body["date_of_birth"] is None
    assert body["gender"] is None
    assert body["city"] is None


def test_get_onboarding_reflects_saved_step_1_data(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    athlete = _existing_athlete(current_onboarding_step=2)
    athlete.athlete_name = "Jane Doe"
    athlete.date_of_birth = date(2005, 4, 12)
    athlete.gender = "Female"
    athlete.city = "Mumbai"
    fake_onboarding_repository.athletes[PHONE_NUMBER] = athlete

    response = wired_client.get(STATUS_ENDPOINT, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["current_onboarding_step"] == 2
    assert body["full_name"] == "Jane Doe"
    assert body["date_of_birth"] == "2005-04-12"
    assert body["gender"] == "Female"
    assert body["city"] == "Mumbai"


# --- PUT /api/v2/onboarding/step-1 ------------------------------------------------


def test_put_step_1_success(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=1)

    response = wired_client.put(STEP_1_ENDPOINT, json=VALID_STEP_1_BODY, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["current_onboarding_step"] == 2
    assert body["full_name"] == "Jane Doe"
    assert body["date_of_birth"] == "2005-04-12"
    assert body["gender"] == "Female"
    assert body["city"] == "Mumbai"

    saved = fake_onboarding_repository.athletes[PHONE_NUMBER]
    assert saved.athlete_name == "Jane Doe"
    assert saved.current_onboarding_step == 2


def test_put_step_1_does_not_create_a_new_athlete(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    response = wired_client.put(STEP_1_ENDPOINT, json=VALID_STEP_1_BODY, headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"
    assert PHONE_NUMBER not in fake_onboarding_repository.athletes


@pytest.mark.parametrize(
    "invalid_body",
    [
        {**VALID_STEP_1_BODY, "fullName": ""},
        {**VALID_STEP_1_BODY, "fullName": "   "},
        {**VALID_STEP_1_BODY, "dateOfBirth": "not-a-date"},
        {**VALID_STEP_1_BODY, "gender": "Alien"},
        {**VALID_STEP_1_BODY, "city": ""},
        {k: v for k, v in VALID_STEP_1_BODY.items() if k != "fullName"},
        {k: v for k, v in VALID_STEP_1_BODY.items() if k != "dateOfBirth"},
        {k: v for k, v in VALID_STEP_1_BODY.items() if k != "gender"},
        {k: v for k, v in VALID_STEP_1_BODY.items() if k != "city"},
    ],
)
def test_put_step_1_rejects_invalid_bodies(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    invalid_body: dict[str, str],
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete()

    response = wired_client.put(STEP_1_ENDPOINT, json=invalid_body, headers=auth_headers)

    assert response.status_code == 422


def test_put_step_1_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.put(STEP_1_ENDPOINT, json=VALID_STEP_1_BODY)
    assert response.status_code == 401


# --- PUT /api/v2/onboarding/step-2 ------------------------------------------------


def test_put_step_2_success(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=2)

    response = wired_client.put(STEP_2_ENDPOINT, json=VALID_STEP_2_BODY, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["current_onboarding_step"] == 3
    assert body["discipline"] == "10m Air Rifle"
    assert body["experience_level"] == "1 - 2 Years (Intermediate)"
    assert body["years_shooting"] == 2
    assert body["academy_id"] == ACADEMY_ID

    saved = fake_onboarding_repository.athletes[PHONE_NUMBER]
    assert saved.weapon_specialization == "10m Air Rifle"
    assert saved.current_onboarding_step == 3


def test_put_step_2_athlete_not_found(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    response = wired_client.put(STEP_2_ENDPOINT, json=VALID_STEP_2_BODY, headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


@pytest.mark.parametrize(
    "invalid_body",
    [
        {k: v for k, v in VALID_STEP_2_BODY.items() if k != "discipline"},
        {**VALID_STEP_2_BODY, "discipline": ""},
        {k: v for k, v in VALID_STEP_2_BODY.items() if k != "experienceLevel"},
        {**VALID_STEP_2_BODY, "experienceLevel": ""},
        {**VALID_STEP_2_BODY, "yearsShooting": -1},
        {k: v for k, v in VALID_STEP_2_BODY.items() if k != "yearsShooting"},
        {k: v for k, v in VALID_STEP_2_BODY.items() if k != "academyId"},
        {**VALID_STEP_2_BODY, "academyId": "not-a-uuid"},
    ],
)
def test_put_step_2_rejects_invalid_bodies(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    invalid_body: dict[str, object],
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=2)

    response = wired_client.put(STEP_2_ENDPOINT, json=invalid_body, headers=auth_headers)

    assert response.status_code == 422


def test_put_step_2_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.put(STEP_2_ENDPOINT, json=VALID_STEP_2_BODY)
    assert response.status_code == 401


# --- PUT /api/v2/onboarding/step-3 ------------------------------------------------


def test_put_step_3_success(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=3)

    response = wired_client.put(STEP_3_ENDPOINT, json=VALID_STEP_3_BODY, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["current_onboarding_step"] == 4
    assert body["average_practice_score"] == 72.5
    assert body["target_score"] == 95.0
    assert body["performance_blockers"] == ["Anxiety", "Inconsistent breathing"]
    assert body["goal_30_day"] == "Improve stance stability"
    assert body["goal_6_month"] == "Qualify for nationals"

    saved = fake_onboarding_repository.athletes[PHONE_NUMBER]
    assert saved.avg_practice_score == 72.5
    assert saved.current_onboarding_step == 4


def test_put_step_3_athlete_not_found(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    response = wired_client.put(STEP_3_ENDPOINT, json=VALID_STEP_3_BODY, headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


@pytest.mark.parametrize(
    "invalid_body",
    [
        {**VALID_STEP_3_BODY, "averagePracticeScore": "not-a-number"},
        {**VALID_STEP_3_BODY, "targetScore": "not-a-number"},
        {**VALID_STEP_3_BODY, "performanceBlockers": "not-a-list"},
        {k: v for k, v in VALID_STEP_3_BODY.items() if k != "goal30Day"},
        {**VALID_STEP_3_BODY, "goal30Day": ""},
        {k: v for k, v in VALID_STEP_3_BODY.items() if k != "goal6Month"},
        {**VALID_STEP_3_BODY, "goal6Month": ""},
    ],
)
def test_put_step_3_rejects_invalid_bodies(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    invalid_body: dict[str, object],
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=3)

    response = wired_client.put(STEP_3_ENDPOINT, json=invalid_body, headers=auth_headers)

    assert response.status_code == 422


def test_put_step_3_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.put(STEP_3_ENDPOINT, json=VALID_STEP_3_BODY)
    assert response.status_code == 401


# --- PUT /api/v2/onboarding/step-4 ------------------------------------------------


def test_put_step_4_creates_athlete_details_when_none_exists(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=4)
    assert ATHLETE_ID not in fake_athlete_details_repository.details

    response = wired_client.put(STEP_4_ENDPOINT, json=VALID_STEP_4_BODY, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["current_onboarding_step"] == 5
    assert body["school_class"] == "9th"
    assert body["school_name"] == "Sri Prakash"
    assert body["academic_performance"] == "80-90%"

    assert ATHLETE_ID in fake_athlete_details_repository.details
    created = fake_athlete_details_repository.details[ATHLETE_ID]
    assert created.class_ == "9th"

    saved_athlete = fake_onboarding_repository.athletes[PHONE_NUMBER]
    assert saved_athlete.current_onboarding_step == 5


def test_put_step_4_updates_existing_athlete_details_without_duplicating(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=4)
    fake_athlete_details_repository.details[ATHLETE_ID] = HamsaTechAthleteDetails(
        athlete_id=ATHLETE_ID, class_="8th", school_name="Old School", academic_performance="50-60%"
    )

    response = wired_client.put(STEP_4_ENDPOINT, json=VALID_STEP_4_BODY, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["school_class"] == "9th"
    assert body["school_name"] == "Sri Prakash"

    # Still exactly one details row for this athlete — updated, not duplicated.
    assert len(fake_athlete_details_repository.details) == 1
    assert fake_athlete_details_repository.details[ATHLETE_ID].class_ == "9th"


def test_put_step_4_athlete_not_found(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    response = wired_client.put(STEP_4_ENDPOINT, json=VALID_STEP_4_BODY, headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


@pytest.mark.parametrize(
    "invalid_body",
    [
        {k: v for k, v in VALID_STEP_4_BODY.items() if k != "class"},
        {**VALID_STEP_4_BODY, "class": ""},
        {k: v for k, v in VALID_STEP_4_BODY.items() if k != "schoolName"},
        {**VALID_STEP_4_BODY, "schoolName": ""},
        {k: v for k, v in VALID_STEP_4_BODY.items() if k != "academicPerformance"},
        {**VALID_STEP_4_BODY, "academicPerformance": ""},
    ],
)
def test_put_step_4_rejects_invalid_bodies(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    invalid_body: dict[str, object],
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=4)

    response = wired_client.put(STEP_4_ENDPOINT, json=invalid_body, headers=auth_headers)

    assert response.status_code == 422


def test_put_step_4_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.put(STEP_4_ENDPOINT, json=VALID_STEP_4_BODY)
    assert response.status_code == 401


# --- GET reflects Steps 2-4 -------------------------------------------------------


def test_get_onboarding_reflects_all_steps(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> None:
    athlete = _existing_athlete(current_onboarding_step=5)
    athlete.athlete_name = "Jane Doe"
    athlete.weapon_specialization = "10m Air Rifle"
    athlete.experience_level = "1 - 2 Years (Intermediate)"
    athlete.years_shooting = 2
    athlete.academy_id = UUID(ACADEMY_ID)
    athlete.avg_practice_score = 72.5
    athlete.target_score = 95.0
    athlete.performance_blockers = ["Anxiety"]
    athlete.goal_30_day = "Improve stance"
    athlete.goal_6_month = "Nationals"
    fake_onboarding_repository.athletes[PHONE_NUMBER] = athlete
    fake_athlete_details_repository.details[ATHLETE_ID] = HamsaTechAthleteDetails(
        athlete_id=ATHLETE_ID, class_="9th", school_name="Sri Prakash", academic_performance="80-90%"
    )

    response = wired_client.get(STATUS_ENDPOINT, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["current_onboarding_step"] == 5
    # Step 1 fields still present, unaffected.
    assert body["full_name"] == "Jane Doe"
    # Step 2
    assert body["discipline"] == "10m Air Rifle"
    assert body["academy_id"] == ACADEMY_ID
    # Step 3
    assert body["target_score"] == 95.0
    assert body["performance_blockers"] == ["Anxiety"]
    # Step 4
    assert body["school_class"] == "9th"
    assert body["academic_performance"] == "80-90%"


# --- PUT /api/v2/onboarding/step-5 ------------------------------------------------


def test_put_step_5_creates_athlete_details_when_none_exists(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=5)
    assert ATHLETE_ID not in fake_athlete_details_repository.details

    response = wired_client.put(STEP_5_ENDPOINT, json=VALID_STEP_5_BODY, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["current_onboarding_step"] == 6
    assert body["diet_type"] == "Mix"
    assert body["outside_food_frequency"] == "Weekly"
    assert body["sleep_time"] == "7hrs"
    assert body["wake_time"] == "5:30 AM"
    assert body["is_onboarding_complete"] is False  # Step 6 not saved yet

    saved = fake_onboarding_repository.athletes[PHONE_NUMBER]
    assert saved.current_onboarding_step == 6
    assert ATHLETE_ID in fake_athlete_details_repository.details


def test_put_step_5_updates_existing_athlete_details_without_duplicating(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=5)
    fake_athlete_details_repository.details[ATHLETE_ID] = HamsaTechAthleteDetails(
        athlete_id=ATHLETE_ID, class_="9th", school_name="Sri Prakash", academic_performance="80-90%"
    )

    response = wired_client.put(STEP_5_ENDPOINT, json=VALID_STEP_5_BODY, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["diet_type"] == "Mix"
    # Step 4 data preserved, not overwritten by Step 5's update.
    assert body["school_class"] == "9th"
    assert body["school_name"] == "Sri Prakash"

    assert len(fake_athlete_details_repository.details) == 1


def test_put_step_5_athlete_not_found(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    response = wired_client.put(STEP_5_ENDPOINT, json=VALID_STEP_5_BODY, headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


@pytest.mark.parametrize(
    "invalid_body",
    [
        {k: v for k, v in VALID_STEP_5_BODY.items() if k != "dietType"},
        {**VALID_STEP_5_BODY, "dietType": ""},
        {k: v for k, v in VALID_STEP_5_BODY.items() if k != "outsideFoodFrequency"},
        {**VALID_STEP_5_BODY, "outsideFoodFrequency": ""},
        {k: v for k, v in VALID_STEP_5_BODY.items() if k != "sleepTime"},
        {**VALID_STEP_5_BODY, "sleepTime": ""},
        {k: v for k, v in VALID_STEP_5_BODY.items() if k != "wakeTime"},
        {**VALID_STEP_5_BODY, "wakeTime": ""},
    ],
)
def test_put_step_5_rejects_invalid_bodies(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    invalid_body: dict[str, object],
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=5)

    response = wired_client.put(STEP_5_ENDPOINT, json=invalid_body, headers=auth_headers)

    assert response.status_code == 422


def test_put_step_5_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.put(STEP_5_ENDPOINT, json=VALID_STEP_5_BODY)
    assert response.status_code == 401


# --- PUT /api/v2/onboarding/step-6 ------------------------------------------------


def test_put_step_6_creates_athlete_details_when_none_exists(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=6)
    assert ATHLETE_ID not in fake_athlete_details_repository.details

    response = wired_client.put(STEP_6_ENDPOINT, json=VALID_STEP_6_BODY, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["friend_circle"] == "Small, supportive"
    assert body["anger_pattern"] == "Rarely, quick to calm down"
    assert body["sadness_pattern"] == "Talks it through"
    assert body["reason_for_shooting"] == "Parents' encouragement, self interest"
    assert body["athlete_goal"] == "Olympic Gold Medal"

    saved = fake_onboarding_repository.athletes[PHONE_NUMBER]
    assert saved.current_onboarding_step == 6
    assert ATHLETE_ID in fake_athlete_details_repository.details


def test_put_step_6_updates_existing_athlete_details_without_duplicating(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=6)
    fake_athlete_details_repository.details[ATHLETE_ID] = HamsaTechAthleteDetails(
        athlete_id=ATHLETE_ID, diet_type="Mix", sleep_time="7hrs"
    )

    response = wired_client.put(STEP_6_ENDPOINT, json=VALID_STEP_6_BODY, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["athlete_goal"] == "Olympic Gold Medal"
    # Step 5 data preserved, not overwritten by Step 6's update.
    assert body["diet_type"] == "Mix"
    assert body["sleep_time"] == "7hrs"

    assert len(fake_athlete_details_repository.details) == 1


def test_put_step_6_athlete_not_found(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
) -> None:
    response = wired_client.put(STEP_6_ENDPOINT, json=VALID_STEP_6_BODY, headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATHLETE_NOT_FOUND"


@pytest.mark.parametrize(
    "invalid_body",
    [
        {k: v for k, v in VALID_STEP_6_BODY.items() if k != "friendCircle"},
        {**VALID_STEP_6_BODY, "friendCircle": ""},
        {k: v for k, v in VALID_STEP_6_BODY.items() if k != "angerPattern"},
        {**VALID_STEP_6_BODY, "angerPattern": ""},
        {k: v for k, v in VALID_STEP_6_BODY.items() if k != "sadnessPattern"},
        {**VALID_STEP_6_BODY, "sadnessPattern": ""},
        {k: v for k, v in VALID_STEP_6_BODY.items() if k != "reasonForShooting"},
        {**VALID_STEP_6_BODY, "reasonForShooting": ""},
        {k: v for k, v in VALID_STEP_6_BODY.items() if k != "athleteGoal"},
        {**VALID_STEP_6_BODY, "athleteGoal": ""},
    ],
)
def test_put_step_6_rejects_invalid_bodies(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    invalid_body: dict[str, object],
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=6)

    response = wired_client.put(STEP_6_ENDPOINT, json=invalid_body, headers=auth_headers)

    assert response.status_code == 422


def test_put_step_6_requires_authentication(wired_client: TestClient) -> None:
    response = wired_client.put(STEP_6_ENDPOINT, json=VALID_STEP_6_BODY)
    assert response.status_code == 401


# --- Onboarding completion ---------------------------------------------------------


def test_step_6_marks_onboarding_complete(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=6)

    response = wired_client.put(STEP_6_ENDPOINT, json=VALID_STEP_6_BODY, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["current_onboarding_step"] == 6
    assert body["is_onboarding_complete"] is True


def test_get_onboarding_reflects_completion_after_step_6(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> None:
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=6)
    fake_athlete_details_repository.details[ATHLETE_ID] = HamsaTechAthleteDetails(
        athlete_id=ATHLETE_ID,
        friend_circle="Small",
        anger_pattern="Rare",
        sadness_pattern="Talks",
        reason_for_shooting="Interest",
        athlete_goal="Nationals",
    )

    response = wired_client.get(STATUS_ENDPOINT, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["current_onboarding_step"] == 6
    assert body["is_onboarding_complete"] is True


def test_get_onboarding_not_complete_before_step_6(
    wired_client: TestClient,
    auth_headers: dict[str, str],
    fake_onboarding_repository: FakeOnboardingRepository,
    fake_athlete_details_repository: FakeAthleteDetailsRepository,
) -> None:
    # current_onboarding_step reads 6 (set by Step 5), but Step 6's own
    # fields haven't been saved yet — must not be reported as complete.
    fake_onboarding_repository.athletes[PHONE_NUMBER] = _existing_athlete(current_onboarding_step=6)
    fake_athlete_details_repository.details[ATHLETE_ID] = HamsaTechAthleteDetails(
        athlete_id=ATHLETE_ID, diet_type="Mix"
    )

    response = wired_client.get(STATUS_ENDPOINT, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["is_onboarding_complete"] is False
