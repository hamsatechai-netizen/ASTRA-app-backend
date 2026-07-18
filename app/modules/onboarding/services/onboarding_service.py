"""
Onboarding business logic — Step 1 (Personal Details) only.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — that already happens during
Verify OTP, see `app.modules.auth.services.user_service.UserService`) and
either reports its current onboarding state or saves Step 1 onto it.
"""

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.onboarding.constants import TOTAL_ONBOARDING_STEPS
from app.modules.onboarding.exceptions import AthleteNotFoundException
from app.modules.onboarding.repositories.onboarding_repository_interface import (
    OnboardingRepositoryInterface,
)
from app.modules.onboarding.schemas.requests import OnboardingStep1Request
from app.modules.onboarding.schemas.responses import OnboardingStatusResponse

_DEFAULT_STEP = 1


class OnboardingService:
    """Resolves onboarding status and applies Step 1 to the authenticated athlete's profile."""

    def __init__(self, repository: OnboardingRepositoryInterface) -> None:
        self._repository = repository

    async def get_status(self, phone_number: str) -> OnboardingStatusResponse:
        """Return the current onboarding state for the athlete matching `phone_number`."""
        athlete = await self._repository.get_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()

        return self._to_response(athlete)

    async def complete_step_1(
        self, phone_number: str, payload: OnboardingStep1Request
    ) -> OnboardingStatusResponse:
        """
        Save Step 1 (Personal Details) onto the existing athlete matching
        `phone_number` and advance `current_onboarding_step` to 2.

        Raises `AthleteNotFoundException` if no athlete profile exists —
        no new athlete is ever created here.
        """
        athlete = await self._repository.get_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()

        athlete = await self._repository.save_step_1(
            athlete,
            full_name=payload.full_name,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender.value,
            city=payload.city,
        )
        return self._to_response(athlete)

    @staticmethod
    def _to_response(athlete: HamsaTechAthlete) -> OnboardingStatusResponse:
        step = athlete.current_onboarding_step or _DEFAULT_STEP
        return OnboardingStatusResponse(
            athlete_id=athlete.athlete_id,
            current_onboarding_step=step,
            is_onboarding_complete=step > TOTAL_ONBOARDING_STEPS,
            full_name=athlete.athlete_name,
            date_of_birth=athlete.date_of_birth,
            gender=athlete.gender,
            city=athlete.city,
        )
