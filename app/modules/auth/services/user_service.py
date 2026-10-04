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

from loguru import logger

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_user import HamsaTechUser
from app.modules.auth.constants import OnboardingStatus
from app.modules.auth.exceptions import (
    AmbiguousAthleteMatchException,
    IdentityConflictException,
    UidAlreadyAssignedException,
)
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

    async def resolve_onboarding_status(self, phone_number: str, user: HamsaTechUser) -> OnboardingStatus:
        """
        Return where the client should route to after a successful login:

        - `phone_number` matches more than one `hamsatech.athletes` row
          (no unique constraint exists on `contact_number` — see the
          Blocker B investigation): `AmbiguousAthleteMatchException` (409)
          is raised immediately, before anything else runs. There is no
          safe way to tell whether this is a new or a returning athlete,
          so nothing is created, linked, or reassigned — see
          `AthleteContactMatch` and the exception's own docstring.
        - No athlete profile exists for `phone_number` yet: create a
          minimal one (establishing the link for future logins), link
          `user.uid` to the newly generated `athlete_id` (see below), and
          return `ONBOARDING_STEP_1`.
        - An athlete profile exists and onboarding is complete (per
          `OnboardingService.is_onboarding_complete`): return `HOME`.
        - An athlete profile exists but onboarding is incomplete: return
          the step matching `athlete.current_onboarding_step`, so the
          client resumes onboarding where the athlete left off.

        Identity linking (new-athlete branch only — a returning athlete's
        `user.uid` is never touched here): `hamsatech.athlete_physiology`
        and `hamsatech.polar_credentials` carry a foreign key from
        `athlete_id` to `hamsatech.users(uid)`, but nothing populated
        `uid` for accounts created through this codebase's signup flow,
        which caused baseline-capture writes to fail with a foreign-key
        violation (see the Baseline FK investigation). `uid` is set to
        the freshly generated `athlete_id` here — the one place that
        knows both, in the same request-scoped transaction as the
        athlete's creation.

        Four cases, evaluated in this order once the new athlete row exists
        (all within the request's single transaction):

        1. `user.uid IS NULL` and no other account holds the new
           `athlete_id`: set `user.uid = athlete_id`. The repository flushes
           the assignment, so any later insert in the same transaction that
           references `users(uid)` already sees it.
        2. `user.uid == athlete_id`: already consistent — idempotent, no
           write is issued.
        3. `user.uid` is non-null and differs: it is never overwritten;
           `IdentityConflictException` (409) is raised.
        4. `user.uid IS NULL` but another `users` row already holds the new
           `athlete_id` as its `uid`: it is never reassigned;
           `UidAlreadyAssignedException` (409) is raised.

        In cases 3 and 4 onboarding does not continue, and the exception's
        propagation out of the request causes `get_db` to roll back the
        whole transaction, including the just-created (not yet committed)
        user and athlete rows.

        Returning athletes (profile already exists) never enter the branch
        above — but if their `user.uid` is still `None` (the accounts
        affected by the Baseline FK investigation that predate this
        linking), a separate, strictly safer self-heal is attempted: see
        `_attempt_returning_athlete_uid_self_heal`. Unlike the four cases
        above, it never raises and never blocks login — repair is
        opportunistic for an account that already works, not a
        precondition for authenticating.
        """
        match = await self._athlete_repository.get_by_contact_number(phone_number)
        if match.is_ambiguous:
            raise AmbiguousAthleteMatchException()

        athlete = match.athlete
        if athlete is None:
            athlete = await self._athlete_repository.create_minimal(phone_number)
            if user.uid is not None and user.uid != athlete.athlete_id:
                raise IdentityConflictException()  # case 3
            if user.uid is None:
                holder = await self._user_repository.get_by_uid(athlete.athlete_id)
                if holder is not None and holder.id != user.id:
                    raise UidAlreadyAssignedException()  # case 4
                await self._user_repository.set_uid_if_absent(user, athlete.athlete_id)  # case 1
            # case 2 (user.uid == athlete.athlete_id): nothing to do — idempotent.
            return OnboardingStatus.ONBOARDING_STEP_1

        await self._attempt_returning_athlete_uid_self_heal(phone_number, user, athlete)

        details = await self._athlete_details_repository.get_by_athlete_id(athlete.athlete_id)
        if OnboardingService.is_onboarding_complete(details):
            return OnboardingStatus.HOME

        step = athlete.current_onboarding_step or _DEFAULT_ONBOARDING_STEP
        return OnboardingStatus(f"ONBOARDING_STEP_{step}")

    async def _attempt_returning_athlete_uid_self_heal(
        self, phone_number: str, user: HamsaTechUser, athlete: HamsaTechAthlete
    ) -> None:
        """
        Best-effort, non-blocking `users.uid` repair for a RETURNING athlete
        (the profile already existed before this login) whose `uid` is still
        `None` — the accounts affected by the Baseline FK investigation that
        predate the new-athlete linking above. Never raises; a returning
        athlete already has a working account, so repair here is strictly
        opportunistic, never a precondition for completing login.

        `athlete_id` (e.g. "ASA001") is this project's permanent athlete
        identifier; `user.uid` is what other tables' foreign keys actually
        reference, and is the thing missing here. Four outcomes, in order:

        (a) `user.uid` is already set — correct or not, it is NEVER
            overwritten (the one absolute rule this method exists to
            enforce), so nothing to repair. This also covers case 2
            ("already correct") as a pure no-op, and makes every repeat
            call idempotent once (b) below has linked it once.
        (b) `user.uid is None`, but more than one `hamsatech.athletes` row
            shares `phone_number` (`count_by_contact_number() != 1`): an
            AMBIGUOUS match — the Blocker B duplicate-contact-number class
            of risk. A phone number is corroborating evidence, never
            sufficient proof, when it doesn't resolve to exactly one
            profile, so this is logged and skipped, not repaired. In
            practice this branch is now defense-in-depth, not the primary
            guard: `resolve_onboarding_status` already refuses to reach
            this method at all when `get_by_contact_number` itself reports
            ambiguity (`AmbiguousAthleteMatchException`). This method's own
            fresh re-check exists so the uid-linking write below is never
            gated solely on a flag computed earlier in the request — a
            future change to `get_by_contact_number` weakening its own
            guard would not, by itself, make an unsafe link possible here.
        (c) `user.uid is None`, exactly one athlete matches, and no other
            `users` row already holds `athlete.athlete_id` as its own
            `uid`: linked via one atomic, race-safe conditional UPDATE
            (`UserRepositoryInterface.try_self_heal_uid`) and logged.
        (d) Same as (c) but another account already holds that uid: never
            reassigned — linking here would either violate the UNIQUE(uid)
            constraint or, worse, silently misattribute this athlete's data
            to the wrong account. Logged as a conflict requiring manual,
            out-of-band investigation (a recovery flow), not auto-repaired.
        """
        if user.uid is not None:
            return  # case (a)

        match_count = await self._athlete_repository.count_by_contact_number(phone_number)
        if match_count != 1:
            logger.warning(
                "uid self-heal skipped for athlete_id={}: {} athlete profiles share this phone "
                "number (ambiguous match, not repaired automatically).",
                athlete.athlete_id,
                match_count,
            )
            return  # case (b)

        healed = await self._user_repository.try_self_heal_uid(user, athlete.athlete_id)
        if healed:
            logger.info(
                "uid self-healed: user_id={} linked to athlete_id={} (returning-athlete repair).",
                user.id,
                athlete.athlete_id,
            )
            return  # case (c)

        logger.warning(
            "uid self-heal skipped for athlete_id={}: already linked to a different account.",
            athlete.athlete_id,
        )
        # case (d)
