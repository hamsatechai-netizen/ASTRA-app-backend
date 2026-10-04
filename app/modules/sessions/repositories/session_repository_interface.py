"""
Sessions repository contract.

Backs the existing `hamsatech.athletes` table (for athlete resolution —
same `get_athlete_by_contact_number` shape as `HrStreamRepositoryInterface`
/ `PsychologyResponseRepositoryInterface`, kept as its own narrow interface
per the Interface Segregation rationale already used throughout this
project) and the existing `hamsatech.sessions` table (one row per training
session).
"""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session


class SessionRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete and creating/completing their training sessions."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def create(self, athlete_id: str, session_type: str | None) -> Session:
        """Insert and return a new `sessions` row for `athlete_id`."""

    @abstractmethod
    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        """Return the `sessions` row with `session_id`, if any."""

    @abstractmethod
    async def complete(self, row: Session, end_time: datetime) -> Session:
        """Set `end_time` on `row` and return it."""
