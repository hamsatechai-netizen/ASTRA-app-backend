"""
Onboarding business logic — Steps 1-4 (Batch 1).

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — that already happens during
Verify OTP, see `app.modules.auth.services.user_service.UserService`) and
either reports its current onboarding state or saves a given step onto
it. Step 4 (Academic Profile) additionally reads/writes the athlete's
`hamsatech.athlete_details` row via `AthleteDetailsRepositoryInterface`,
creating it once if it doesn't exist yet and never duplicating it.
"""

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_athlete_details import HamsaTechAthleteDetails
from app.modules.onboarding.constants import TOTAL_ONBOARDING_STEPS
from app.modules.onboarding.exceptions import AthleteNotFoundException
from app.modules.onboarding.repositories.athlete_details_repository_interface import (
    AthleteDetailsRepositoryInterface,
)
from app.modules.onboarding.repositories.onboarding_repository_interface import (
    OnboardingRepositoryInterface,
)
from app.modules.onboarding.schemas.requests import (
    OnboardingStep1Request,
    OnboardingStep2Request,
    OnboardingStep3Request,
    OnboardingStep4Request,
)
from app.modules.onboarding.schemas.responses import OnboardingStatusResponse

_DEFAULT_STEP = 1
_STEP_5 = 5


class OnboardingService:
    """Resolves onboarding status and applies Steps 1-4 to the authenticated athlete's profile."""

    def __init__(
        self,
        repository: OnboardingRepositoryInterface,
        athlete_details_repository: AthleteDetailsRepositoryInterface,
    ) -> None:
        self._repository = repository
        self._athlete_details_repository = athlete_details_repository

    async def get_status(self, phone_number: str) -> OnboardingStatusResponse:
        """Return the current onboarding state for the athlete matching `phone_number`."""
        athlete = await self._repository.get_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()

        details = await self._athlete_details_repository.get_by_athlete_id(athlete.athlete_id)
        return self._to_response(athlete, details)

    async def complete_step_1(
        self, phone_number: str, payload: OnboardingStep1Request
    ) -> OnboardingStatusResponse:
        """
        Save Step 1 (Personal Details) onto the existing athlete matching
        `phone_number` and advance `current_onboarding_step` to 2.

        Raises `AthleteNotFoundException` if no athlete profile exists —
        no new athlete is ever created here.
        """
        athlete = await self._get_athlete_or_raise(phone_number)

        athlete = await self._repository.save_step_1(
            athlete,
            full_name=payload.full_name,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender.value,
            city=payload.city,
        )
        details = await self._athlete_details_repository.get_by_athlete_id(athlete.athlete_id)
        return self._to_response(athlete, details)

    async def complete_step_2(
        self, phone_number: str, payload: OnboardingStep2Request
    ) -> OnboardingStatusResponse:
        """
        Save Step 2 (Athletic Background) onto the existing athlete matching
        `phone_number` and advance `current_onboarding_step` to 3.
        """
        athlete = await self._get_athlete_or_raise(phone_number)

        athlete = await self._repository.save_step_2(
            athlete,
            discipline=payload.discipline,
            experience_level=payload.experience_level,
            years_shooting=payload.years_shooting,
            academy_id=payload.academy_id,
        )
        details = await self._athlete_details_repository.get_by_athlete_id(athlete.athlete_id)
        return self._to_response(athlete, details)

    async def complete_step_3(
        self, phone_number: str, payload: OnboardingStep3Request
    ) -> OnboardingStatusResponse:
        """
        Save Step 3 (Track Your Performance) onto the existing athlete
        matching `phone_number` and advance `current_onboarding_step` to 4.
        """
        athlete = await self._get_athlete_or_raise(phone_number)

        athlete = await self._repository.save_step_3(
            athlete,
            average_practice_score=payload.average_practice_score,
            target_score=payload.target_score,
            performance_blockers=payload.performance_blockers,
            goal_30_day=payload.goal_30_day,
            goal_6_month=payload.goal_6_month,
        )
        details = await self._athlete_details_repository.get_by_athlete_id(athlete.athlete_id)
        return self._to_response(athlete, details)

    async def complete_step_4(
        self, phone_number: str, payload: OnboardingStep4Request
    ) -> OnboardingStatusResponse:
        """
        Save Step 4 (Academic Profile) onto the athlete's `athlete_details`
        row matching `phone_number` and advance `current_onboarding_step`
        to 5. Creates the `athlete_details` row once if none exists yet;
        never creates a duplicate.
        """
        athlete = await self._get_athlete_or_raise(phone_number)

        details = await self._athlete_details_repository.get_by_athlete_id(athlete.athlete_id)
        if details is None:
            details = await self._athlete_details_repository.create(
                athlete.athlete_id,
                class_=payload.class_,
                school_name=payload.school_name,
                academic_performance=payload.academic_performance,
            )
        else:
            details = await self._athlete_details_repository.update(
                details,
                class_=payload.class_,
                school_name=payload.school_name,
                academic_performance=payload.academic_performance,
            )

        athlete = await self._repository.advance_onboarding_step(athlete, _STEP_5)
        return self._to_response(athlete, details)

    async def _get_athlete_or_raise(self, phone_number: str) -> HamsaTechAthlete:
        athlete = await self._repository.get_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        return athlete

    @staticmethod
    def _to_response(
        athlete: HamsaTechAthlete, details: HamsaTechAthleteDetails | None
    ) -> OnboardingStatusResponse:
        step = athlete.current_onboarding_step or _DEFAULT_STEP
        return OnboardingStatusResponse(
            athlete_id=athlete.athlete_id,
            current_onboarding_step=step,
            is_onboarding_complete=step > TOTAL_ONBOARDING_STEPS,
            full_name=athlete.athlete_name,
            date_of_birth=athlete.date_of_birth,
            gender=athlete.gender,
            city=athlete.city,
            discipline=athlete.weapon_specialization,
            experience_level=athlete.experience_level,
            years_shooting=athlete.years_shooting,
            academy_id=athlete.academy_id,
            average_practice_score=athlete.avg_practice_score,
            target_score=athlete.target_score,
            performance_blockers=athlete.performance_blockers,
            goal_30_day=athlete.goal_30_day,
            goal_6_month=athlete.goal_6_month,
            school_class=details.class_ if details is not None else None,
            school_name=details.school_name if details is not None else None,
            academic_performance=details.academic_performance if details is not None else None,
        )
