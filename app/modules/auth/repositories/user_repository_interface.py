"""
User identity repository contract.

Backs the existing `hamsatech.users` table (see `app.models.hamsatech_user`).
Narrow by design (Interface Segregation, same rationale as
`OTPRepositoryInterface`): only the phone-identity operations Phase 3
needs, nothing about the wider `hamsatech` schema.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.models.hamsatech_user import HamsaTechUser


class UserRepositoryInterface(ABC):
    """Abstract contract for reading and persisting phone-verified user identities."""

    @abstractmethod
    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        """Return the user identity for `phone_number`, or None if no account exists."""

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> HamsaTechUser | None:
        """Return the user identity for `user_id`, or None if no account exists."""

    @abstractmethod
    async def create(self, phone_number: str) -> HamsaTechUser:
        """Create a new user identity for `phone_number` with the minimum required fields."""

    @abstractmethod
    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        """Set `phone_verified_at` and `last_login_at` on `user` to the current time."""

    async def set_uid_if_absent(self, user: HamsaTechUser, uid: str) -> None:
        """
        Set `user.uid = uid`, but only if `user.uid` is currently `None`.

        Deliberately concrete, not `@abstractmethod` — unlike every other
        method on this interface. `UserRepositoryInterface` is implemented
        by a separate in-memory fake in every module's test suite that
        exercises an authenticated endpoint (checkin, streak, dashboard,
        sessions, baseline, etc. — 14+ files, all via `get_current_athlete`
        needing `get_by_id`). Making this abstract would force a stub
        override into every one of those unrelated files just to keep them
        instantiable. This default body is already correct behavior for
        every one of those plain-Python-object fakes; only the real,
        SQLAlchemy-backed `UserRepository` needs to override it, to also
        flush. See `app.modules.auth.services.user_service.UserService
        .resolve_onboarding_status` for the caller and the conflict
        safeguard around it — this method's job is only the non-overwrite
        guarantee, not conflict detection.
        """
        if user.uid is None:
            user.uid = uid

    async def get_by_uid(self, uid: str) -> HamsaTechUser | None:
        """
        Return the user whose `uid` equals `uid`, or `None` if no account holds it.

        Deliberately concrete, not `@abstractmethod`, for exactly the same
        reason as `set_uid_if_absent` above: the many per-module in-memory
        fakes of this interface never model `uid` ownership, and `None`
        ("nobody holds this uid") is the correct answer for every one of
        them. Only the real `UserRepository` overrides this with a query.
        Used by `UserService.resolve_onboarding_status` to detect, *before*
        assignment, that a freshly generated `athlete_id` is already some
        other account's `uid` (`users_uid_key` is UNIQUE) and raise a
        controlled conflict instead of surfacing an IntegrityError as a 500.
        """
        return None

    async def try_self_heal_uid(self, user: HamsaTechUser, candidate_uid: str) -> bool:
        """
        Atomically link `user.uid = candidate_uid`, but only if `user.uid` is
        currently `None` and no other `users` row already holds
        `candidate_uid`. Returns whether this call performed the link.

        Never overwrites an existing `uid` (matching or not) and never
        raises for either guard failing — the caller (`UserService`'s
        returning-athlete self-heal) treats "not linked" as a normal,
        loggable outcome, not an error, so a returning athlete's login is
        never blocked by a repair that couldn't proceed.

        Deliberately concrete, not `@abstractmethod`: the default composes
        the two guards this interface already exposes —
        `get_by_uid` (is `candidate_uid` already claimed?) and
        `set_uid_if_absent` (never overwrite) — so any fake that already
        overrides `get_by_uid` to model uid ownership (as
        `test_verify_otp.FakeUserRepository` does) gets a correct conflict
        check here for free, with no third override needed. This default is
        two Python calls, not one atomic statement — adequate for every
        in-memory fake, which has no concurrent callers. Only the real,
        SQLAlchemy-backed `UserRepository` needs single-statement atomicity
        (a compare-and-swap `UPDATE ... WHERE uid IS NULL AND NOT EXISTS
        (...)`), since only it faces concurrent requests.
        """
        if user.uid is not None:
            return False
        if await self.get_by_uid(candidate_uid) is not None:
            return False
        await self.set_uid_if_absent(user, candidate_uid)
        return user.uid == candidate_uid
