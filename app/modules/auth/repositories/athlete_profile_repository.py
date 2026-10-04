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

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.auth.repositories.athlete_profile_repository_interface import (
    AthleteContactMatch,
    AthleteProfileRepositoryInterface,
)

# Arbitrary but fixed key identifying this advisory lock — must stay
# constant so concurrent transactions actually contend on the same lock.
_ATHLETE_ID_LOCK_KEY = "hamsatech.athletes.athlete_id"


class AthleteProfileRepository(AthleteProfileRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_contact_number(self, phone_number: str) -> AthleteContactMatch:
        # `.scalars().all()` + a length check, never `.scalar_one_or_none()`: the
        # latter raises `MultipleResultsFound` the moment `contact_number` is
        # duplicated (no unique constraint exists on it — see the Blocker B
        # investigation), which used to crash the whole verify-otp request as an
        # unhandled 500. This must never raise here; ambiguity is reported back
        # to the caller as data (`AthleteContactMatch.is_ambiguous`), not as an
        # exception, so `UserService` can reject it safely and deterministically
        # instead of the database driver rejecting it violently.
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        rows = result.scalars().all()
        if len(rows) > 1:
            return AthleteContactMatch(athlete=None, is_ambiguous=True)
        return AthleteContactMatch(athlete=rows[0] if rows else None, is_ambiguous=False)

    async def count_by_contact_number(self, phone_number: str) -> int:
        # An independent, defense-in-depth re-check for UserService's uid
        # self-heal guard specifically — see AthleteProfileRepositoryInterface
        # .count_by_contact_number's docstring for why this stays separate from
        # get_by_contact_number's own (now equally safe) ambiguity detection.
        result = await self._session.execute(
            select(func.count())
            .select_from(HamsaTechAthlete)
            .where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one()

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
