"""Academy listing business logic — a thin pass-through onto DTOs."""

from app.modules.academies.repositories.academy_repository_interface import AcademyRepositoryInterface
from app.modules.academies.schemas.responses import AcademyResponse


class AcademyService:
    """Lists academies for the athlete to choose from during onboarding Step 2."""

    def __init__(self, repository: AcademyRepositoryInterface) -> None:
        self._repository = repository

    async def list_academies(self) -> list[AcademyResponse]:
        """Return every academy, or an empty list if none exist (never a 404)."""
        academies = await self._repository.get_all()
        return [
            AcademyResponse(
                academy_id=academy.academy_id, academy_name=academy.academy_name, location=academy.location
            )
            for academy in academies
        ]
