"""
Concrete user-identity repository (SQLAlchemy) against the existing,
externally-owned `hamsatech.users` table. Only ever flushes, never
commits — the request-scoped `AsyncSession` from
`app.dependencies.database.get_db` owns the transaction boundary.
"""

from uuid import UUID

from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_user import HamsaTechUser
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.utils.datetime import utc_now


class UserRepository(UserRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_phone(self, phone_number: str) -> HamsaTechUser | None:
        result = await self._session.execute(
            select(HamsaTechUser).where(HamsaTechUser.phone_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> HamsaTechUser | None:
        result = await self._session.execute(select(HamsaTechUser).where(HamsaTechUser.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_uid(self, uid: str) -> HamsaTechUser | None:
        # `uid` is UNIQUE (`users_uid_key`), so at most one row can match.
        result = await self._session.execute(select(HamsaTechUser).where(HamsaTechUser.uid == uid))
        return result.scalar_one_or_none()

    async def create(self, phone_number: str) -> HamsaTechUser:
        user = HamsaTechUser(phone_number=phone_number)
        self._session.add(user)
        await self._session.flush()
        return user

    async def mark_verified_and_logged_in(self, user: HamsaTechUser) -> None:
        # `hamsatech.users` timestamps are naive ("timestamp without time
        # zone"), unlike this project's own timezone-aware columns.
        now = utc_now().replace(tzinfo=None)
        user.phone_verified_at = now
        user.last_login_at = now
        await self._session.flush()

    async def set_uid_if_absent(self, user: HamsaTechUser, uid: str) -> None:
        if user.uid is not None:
            return
        user.uid = uid
        await self._session.flush()

    async def try_self_heal_uid(self, user: HamsaTechUser, candidate_uid: str) -> bool:
        """
        Single atomic conditional UPDATE: `WHERE id = user.id AND uid IS NULL
        AND NOT EXISTS (... uid = candidate_uid ...)`. Race-safe against a
        concurrent call for the SAME user (a second concurrent attempt just
        updates zero rows — idempotent) purely via the WHERE clause.

        A genuine concurrent race for the SAME candidate_uid across TWO
        DIFFERENT user rows is a separate case: under READ COMMITTED, both
        transactions' NOT EXISTS checks can pass before either commits, so
        the second UPDATE to actually commit hits the `users_uid_key`
        UNIQUE constraint instead of cleanly matching zero rows. The whole
        statement runs inside a SAVEPOINT (`begin_nested`) specifically so
        that outcome — an IntegrityError — rolls back only this statement,
        never the caller's own (larger) request transaction, and is treated
        exactly like any other "didn't win" outcome: return False, no raise.
        """
        try:
            async with self._session.begin_nested():
                result = await self._session.execute(
                    update(HamsaTechUser)
                    .where(
                        HamsaTechUser.id == user.id,
                        HamsaTechUser.uid.is_(None),
                        ~exists().where(HamsaTechUser.uid == candidate_uid),
                    )
                    .values(uid=candidate_uid)
                    .returning(HamsaTechUser.uid)
                )
                healed_uid = result.scalar_one_or_none()
        except IntegrityError:
            return False
        if healed_uid is None:
            return False
        user.uid = healed_uid
        return True
