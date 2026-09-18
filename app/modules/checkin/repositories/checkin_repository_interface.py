"""
Daily check-in repository contract.

Backs the existing `hamsatech.athletes` table (for athlete resolution —
same `get_athlete_by_contact_number` shape as every sibling module's
repository) and this project's own `hamsatech.daily_checkins` table (one
row per `(athlete_id, checkin_date)` — that pair is UNIQUE, so writes are
upserts, not plain inserts).
"""

from abc import ABC, abstractmethod
from datetime import date

from app.models.daily_checkin import DailyCheckin
from app.models.hamsatech_athlete import HamsaTechAthlete


class CheckinRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete and upserting their daily check-in."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
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
        """
        Insert a new `daily_checkins` row for `(athlete_id, checkin_date)`, or
        update the existing one — that pair is UNIQUE, so a second
        submission on the same day overwrites rather than duplicating or
        erroring. `id`/`created_at` are preserved on update; `updated_at`
        always reflects the time of this call.
        """
