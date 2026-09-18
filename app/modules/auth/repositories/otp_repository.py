"""
Concrete OTP repository (SQLAlchemy / Supabase Postgres).

Implements `OTPRepositoryInterface` against the `otp_challenges` table.
Only ever flushes, never commits — the request-scoped `AsyncSession` from
`app.dependencies.database.get_db` owns the transaction boundary and
commits (or rolls back, e.g. if SMS delivery subsequently fails) once the
route completes — with ONE deliberate exception: `increment_attempts`,
which must survive the rollback that follows a failed verification and
therefore commits in its own short transaction (see its docstring).
"""

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.otp_challenge import OTPChallenge
from app.modules.auth.repositories.otp_repository_interface import OTPRepositoryInterface


class OTPRepository(OTPRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_phone(self, phone_number: str) -> OTPChallenge | None:
        result = await self._session.execute(
            select(OTPChallenge).where(OTPChallenge.phone_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def upsert(self, phone_number: str, otp_hash: str, expires_at: datetime) -> OTPChallenge:
        existing = await self.get_by_phone(phone_number)
        if existing is not None:
            existing.otp_hash = otp_hash
            existing.expires_at = expires_at
            existing.attempts = 0
            challenge = existing
        else:
            challenge = OTPChallenge(
                phone_number=phone_number,
                otp_hash=otp_hash,
                expires_at=expires_at,
                attempts=0,
            )
            self._session.add(challenge)

        await self._session.flush()
        return challenge

    async def increment_attempts(self, phone_number: str) -> int:
        """
        Increment `attempts` for `phone_number`'s challenge, durably, and return the new value.

        Why this commits when nothing else here does: `OTPService.verify_otp`
        calls this and then raises `InvalidOTPException`. That exception
        leaves the request, and `get_db` rolls the request-scoped session
        back — so an increment merely flushed into that session was discarded
        every time, and the five-attempt lockout never engaged (found by the
        isolated Postgres smoke test: seven wrong codes left `attempts` at 0).

        The increment therefore runs, and commits, in its own short
        transaction on a separate pooled connection taken from the session's
        engine. It is a single atomic `attempts = attempts + 1` UPDATE, so
        concurrent wrong attempts cannot lose increments either. Nothing
        pending in the request session is committed by this call; the
        request's own rollback still discards everything else, exactly as
        before. `updated_at` is bumped by the column's `onupdate`, matching
        the previous ORM-flush behaviour. Returns 0 if no challenge exists.
        """
        bind = self._session.bind
        if not isinstance(bind, AsyncEngine):
            raise RuntimeError("OTPRepository.increment_attempts requires a session bound to an AsyncEngine.")
        async with bind.begin() as connection:
            result = await connection.execute(
                update(OTPChallenge)
                .where(OTPChallenge.phone_number == phone_number)
                .values(attempts=OTPChallenge.attempts + 1)
                .returning(OTPChallenge.attempts)
            )
            attempts = result.scalar_one_or_none()
        return attempts if attempts is not None else 0

    async def delete_by_phone(self, phone_number: str) -> None:
        await self._session.execute(delete(OTPChallenge).where(OTPChallenge.phone_number == phone_number))
        await self._session.flush()
