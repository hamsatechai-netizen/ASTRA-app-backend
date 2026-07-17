"""
Concrete athlete-profile repository (SQLAlchemy) against the existing
`hamsatech.athletes` table.

`athlete_id` follows an externally-established "ASA" + zero-padded
sequence convention with no database sequence or default backing it —
nothing in this codebase created the existing rows, so nothing here can
rely on Postgres to hand out the next value safely. `_generate_next_athlete_id`
takes a transaction-scoped Postgres advisory lock (`pg_advisory_xact_lock`)
before computing MAX+1, so two concurrent signups can't compute the same
next ID; the lock releases automatically at commit or rollback — no
schema change required.
"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.auth.repositories.athlete_profile_repository_interface import (
    AthleteProfileRepositoryInterface,
)

# Arbitrary but fixed key identifying this advisory lock — must stay
# constant so concurrent transactions actually contend on the same lock.
_ATHLETE_ID_LOCK_KEY = "hamsatech.athletes.athlete_id"


class AthleteProfileRepository(AthleteProfileRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def create_minimal(self, phone_number: str) -> HamsaTechAthlete:
        athlete_id = await self._generate_next_athlete_id()
        athlete = HamsaTechAthlete(athlete_id=athlete_id, contact_number=phone_number)
        self._session.add(athlete)
        await self._session.flush()
        return athlete

    async def _generate_next_athlete_id(self) -> str:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": _ATHLETE_ID_LOCK_KEY}
        )
        result = await self._session.execute(
            text(
                "SELECT MAX(CAST(SUBSTRING(athlete_id FROM 4) AS INTEGER)) "
                "FROM hamsatech.athletes WHERE athlete_id ~ '^ASA[0-9]+$'"
            )
        )
        max_num = result.scalar() or 0
        return f"ASA{max_num + 1:03d}"
