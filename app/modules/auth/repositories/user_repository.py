"""
Concrete user-identity repository (SQLAlchemy) against the existing,
externally-owned `hamsatech.users` table. Only ever flushes, never
commits — the request-scoped `AsyncSession` from
`app.dependencies.database.get_db` owns the transaction boundary.
"""

from sqlalchemy import select
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
