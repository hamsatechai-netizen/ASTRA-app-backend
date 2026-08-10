"""
Concrete HR-stream repository (SQLAlchemy) against the existing
`hamsatech.athletes` and `hamsatech.hr_stream` tables. Only ever flushes,
never commits — the request-scoped `AsyncSession` from
`app.dependencies.database.get_db` owns the transaction boundary.
"""

from collections.abc import Sequence
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hr_stream import HrStream
from app.modules.heart_rate.repositories.hr_stream_repository_interface import (
    HrSampleRecord,
    HrStreamRepositoryInterface,
)


class HrStreamRepository(HrStreamRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def create_many(self, athlete_id: str, samples: Sequence[HrSampleRecord]) -> int:
        rows = [
            HrStream(
                athlete_id=athlete_id,
                session_id=sample.session_id,
                recorded_at=sample.recorded_at.astimezone(UTC).replace(tzinfo=None),
                heart_rate=sample.heart_rate,
                rr_interval=sample.rr_interval,
            )
            for sample in samples
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return len(rows)
