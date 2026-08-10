"""
Academy repository contract.

Backs the existing `hamsatech.academies` table (see
`app.models.hamsatech_academy`). Read-only by design — nothing in this
project creates, updates, or deletes academies.
"""

from abc import ABC, abstractmethod

from app.models.hamsatech_academy import HamsaTechAcademy


class AcademyRepositoryInterface(ABC):
    """Abstract contract for reading academy records."""

    @abstractmethod
    async def get_all(self) -> list[HamsaTechAcademy]:
        """Return every academy record, ordered by name. Empty list if none exist."""
