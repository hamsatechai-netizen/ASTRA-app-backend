"""
User/athlete-identity business logic.

Wraps `UserRepositoryInterface` (`hamsatech.users`) and
`AthleteProfileRepositoryInterface` (`hamsatech.athletes`) into the two
decisions Verify OTP needs: resolve-or-create the phone-verified
identity, and determine onboarding status.

Onboarding completion is not re-derived here: it reuses
`OnboardingService.is_onboarding_complete`, the same check the onboarding
module itself uses (see `app.modules.onboarding.services.onboarding_service`),
so the two modules can never disagree about what "complete" means.
"""

from app.models.hamsatech_user import HamsaTechUser
from app.modules.auth.constants import OnboardingStatus
from app.modules.auth.repositories.athlete_profile_repository_interface import (
    AthleteProfileRepositoryInterface,
)
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.onboarding.repositories.athlete_details_repository_interface import (
    AthleteDetailsRepositoryInterface,
)
from app.modules.onboarding.services.onboarding_service import OnboardingService

_DEFAULT_ONBOARDING_STEP = 1


class UserService:
    """Resolves the phone-verified user identity and athlete-profile onboarding status."""

    def __init__(
        self,
        user_repository: UserRepositoryInterface,
        athlete_repository: AthleteProfileRepositoryInterface,
        athlete_details_repository: AthleteDetailsRepositoryInterface,
    ) -> None:
        self._user_repository = user_repository
        self._athlete_repository = athlete_repository
        self._athlete_details_repository = athlete_details_repository

    async def get_or_create_user(self, phone_number: str) -> tuple[HamsaTechUser, bool]:
        """Return `(user, is_new_user)` for `phone_number`, creating a minimal row if none exists."""
        user = await self._user_repository.get_by_phone(phone_number)
        is_new_user = user is None
        if user is None:
            user = await self._user_repository.create(phone_number)

        await self._user_repository.mark_verified_and_logged_in(user)
        return user, is_new_user

    async def resolve_onboarding_status(self, phone_number: str) -> OnboardingStatus:
        """
        Return where the client should route to after a successful login:

        - No athlete profile exists for `phone_number` yet: create a
          minimal one (establishing the link for future logins) and
          return `ONBOARDING_STEP_1`.
        - An athlete profile exists and onboarding is complete (per
          `OnboardingService.is_onboarding_complete`): return `HOME`.
        - An athlete profile exists but onboarding is incomplete: return
          the step matching `athlete.current_onboarding_step`, so the
          client resumes onboarding where the athlete left off.
        """
        athlete = await self._athlete_repository.get_by_contact_number(phone_number)
        if athlete is None:
            await self._athlete_repository.create_minimal(phone_number)
            return OnboardingStatus.ONBOARDING_STEP_1

        details = await self._athlete_details_repository.get_by_athlete_id(athlete.athlete_id)
        if OnboardingService.is_onboarding_complete(details):
            return OnboardingStatus.HOME

        step = athlete.current_onboarding_step or _DEFAULT_ONBOARDING_STEP
        return OnboardingStatus(f"ONBOARDING_STEP_{step}")
