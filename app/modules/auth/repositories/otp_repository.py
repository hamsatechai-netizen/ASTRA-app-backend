"""
Concrete OTP repository (SQLAlchemy / Supabase Postgres).

Implements `OTPRepositoryInterface` against the `otp_challenges` table.
Only ever flushes, never commits — the request-scoped `AsyncSession` from
`app.dependencies.database.get_db` owns the transaction boundary and
commits (or rolls back, e.g. if SMS delivery subsequently fails) once the
route completes.
"""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

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
        existing = await self.get_by_phone(phone_number)
        if existing is None:
            return 0
        existing.attempts += 1
        await self._session.flush()
        return existing.attempts

    async def delete_by_phone(self, phone_number: str) -> None:
        await self._session.execute(delete(OTPChallenge).where(OTPChallenge.phone_number == phone_number))
        await self._session.flush()
