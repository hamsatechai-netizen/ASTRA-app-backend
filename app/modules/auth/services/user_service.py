"""
User/athlete-identity business logic.

Wraps `UserRepositoryInterface` (`hamsatech.users`) and
`AthleteProfileRepositoryInterface` (`hamsatech.athletes`) into the two
decisions Verify OTP needs: resolve-or-create the phone-verified
identity, and determine onboarding status.
"""

from app.models.hamsatech_user import HamsaTechUser
from app.modules.auth.constants import OnboardingStatus
from app.modules.auth.repositories.athlete_profile_repository_interface import (
    AthleteProfileRepositoryInterface,
)
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface


class UserService:
    """Resolves the phone-verified user identity and athlete-profile onboarding status."""

    def __init__(
        self,
        user_repository: UserRepositoryInterface,
        athlete_repository: AthleteProfileRepositoryInterface,
    ) -> None:
        self._user_repository = user_repository
        self._athlete_repository = athlete_repository

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
        Return `HOME` if an athlete profile already exists for `phone_number`
        (matched via `contact_number`); otherwise create a minimal one
        (establishing that link for future logins) and return
        `ONBOARDING_STEP_1`.
        """
        athlete = await self._athlete_repository.get_by_contact_number(phone_number)
        if athlete is not None:
            return OnboardingStatus.HOME

        await self._athlete_repository.create_minimal(phone_number)
        return OnboardingStatus.ONBOARDING_STEP_1
