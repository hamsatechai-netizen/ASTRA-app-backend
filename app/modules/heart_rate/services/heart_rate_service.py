"""
Heart-rate ingestion business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition
`OnboardingService`/`PsychologyAssessmentService` rely on) and writes the
given batch of HR samples into `hamsatech.hr_stream` against that
athlete's `athlete_id`. `athlete_id` is never taken from the request body
— it is always resolved server-side from the authenticated identity, so a
caller can only ever write HR samples for themselves.
"""

from app.modules.heart_rate.exceptions import AthleteNotFoundException
from app.modules.heart_rate.repositories.hr_stream_repository_interface import (
    HrSampleRecord,
    HrStreamRepositoryInterface,
)
from app.modules.heart_rate.schemas.requests import HrSampleBatchRequest
from app.modules.heart_rate.schemas.responses import HrSampleBatchResponse


class HeartRateService:
    """Resolves the authenticated athlete and persists their HR sample batches."""

    def __init__(self, repository: HrStreamRepositoryInterface) -> None:
        self._repository = repository

    async def record_samples(
        self, phone_number: str, payload: HrSampleBatchRequest
    ) -> HrSampleBatchResponse:
        """Insert every sample in `payload` for the athlete matching `phone_number`."""
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()

        samples = [
            HrSampleRecord(
                session_id=item.session_id,
                recorded_at=item.recorded_at,
                heart_rate=item.heart_rate,
                rr_interval=item.rr_interval,
            )
            for item in payload.samples
        ]
        accepted = await self._repository.create_many(athlete.athlete_id, samples)
        return HrSampleBatchResponse(accepted=accepted)
