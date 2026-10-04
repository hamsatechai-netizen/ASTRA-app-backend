"""
Concrete streak repository (SQLAlchemy), read-only, against the existing
`hamsatech.athletes` and `hamsatech.sessions` tables. No new table, column,
or index — `cast(Session.start_time, Date)` computes the UTC calendar date
at query time.
"""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import Date, cast, distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.modules.streak.repositories.streak_repository_interface import StreakRepositoryInterface


class StreakRepository(StreakRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def get_completed_session_dates(self, athlete_id: str, on_or_before: date) -> Sequence[date]:
        session_date = cast(Session.start_time, Date)
        result = await self._session.execute(
            select(distinct(session_date))
            .where(
                Session.athlete_id == athlete_id,
                Session.end_time.is_not(None),
                session_date <= on_or_before,
            )
            .order_by(session_date.desc())
        )
        return result.scalars().all()
