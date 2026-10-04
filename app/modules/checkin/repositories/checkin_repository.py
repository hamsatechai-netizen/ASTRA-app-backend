"""
Concrete daily check-in repository (SQLAlchemy) against the existing
`hamsatech.athletes` table and this project's own `hamsatech.daily_checkins`
table. Only ever flushes, never commits — the request-scoped `AsyncSession`
from `app.dependencies.database.get_db` owns the transaction boundary.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_checkin import DailyCheckin
from app.models.hamsatech_athlete import HamsaTechAthlete
from app.modules.checkin.repositories.checkin_repository_interface import CheckinRepositoryInterface
from app.utils.datetime import utc_now


class CheckinRepository(CheckinRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def upsert_checkin(
        self,
        *,
        athlete_id: str,
        checkin_date: date,
        mood: int,
        energy_level: int,
        sleep_band: str,
        tags: list[str] | None,
        notes: str | None,
    ) -> DailyCheckin:
        now = utc_now().replace(tzinfo=None)
        # `id`/`created_at` are deliberately omitted from `set_` — their DB
        # defaults apply only on insert; on conflict they're absent from
        # `set_` too, so an existing row's identity/created_at is preserved.
        # `updated_at` is explicitly set on every call (its own DB default
        # only fires on INSERT, same documented gotcha as
        # `hamsatech.shooting_session_log.updated_at`).
        insert_stmt = pg_insert(DailyCheckin).values(
            athlete_id=athlete_id,
            checkin_date=checkin_date,
            mood=mood,
            energy_level=energy_level,
            sleep_band=sleep_band,
            tags=tags,
            notes=notes,
            updated_at=now,
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[DailyCheckin.athlete_id, DailyCheckin.checkin_date],
            set_={
                "mood": insert_stmt.excluded.mood,
                "energy_level": insert_stmt.excluded.energy_level,
                "sleep_band": insert_stmt.excluded.sleep_band,
                "tags": insert_stmt.excluded.tags,
                "notes": insert_stmt.excluded.notes,
                "updated_at": insert_stmt.excluded.updated_at,
            },
        ).returning(DailyCheckin)
        result = await self._session.execute(upsert_stmt)
        await self._session.flush()
        row: DailyCheckin = result.scalar_one()
        return row
