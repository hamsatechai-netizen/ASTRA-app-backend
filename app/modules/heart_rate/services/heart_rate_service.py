"""
Heart-rate ingestion and read-back business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition
`OnboardingService`/`PsychologyAssessmentService` rely on) and writes the
given batch of HR samples into `hamsatech.hr_stream` against that
athlete's `athlete_id`. `athlete_id` is never taken from the request body
— it is always resolved server-side from the authenticated identity, so a
caller can only ever write HR samples for themselves.

Every sample's `session_id` is validated against `hamsatech.sessions`
before insert: the session must exist and must belong to the authenticated
athlete, so a caller can never attach HR samples to a nonexistent or
another athlete's session.

`get_session_hr` reads a session's HR back, enforcing the same
resolve-athlete / path-athlete-match / session-exists / session-ownership
sequence `SessionService.complete_session` already uses.
"""

from collections.abc import Sequence
from statistics import fmean
from uuid import UUID

from app.modules.heart_rate.exceptions import (
    AthleteNotFoundException,
    ForbiddenException,
    SessionNotFoundException,
)
from app.modules.heart_rate.repositories.hr_stream_repository_interface import (
    HrSampleRecord,
    HrStreamRepositoryInterface,
)
from app.modules.heart_rate.schemas.requests import HrSampleBatchRequest
from app.modules.heart_rate.schemas.responses import HrPointResponse, HrSampleBatchResponse, SessionHrResponse

# Chart points are downsampled server-side to this many, at most — evenly
# strided across the full ordered sample set, always including the first
# and last sample so the chart's time range is never truncated.
_MAX_CHART_POINTS = 120


class HeartRateService:
    """Resolves the authenticated athlete and reads/persists their HR sample batches."""

    def __init__(self, repository: HrStreamRepositoryInterface) -> None:
        self._repository = repository

    async def record_samples(self, phone_number: str, payload: HrSampleBatchRequest) -> HrSampleBatchResponse:
        """Insert every sample in `payload` for the athlete matching `phone_number`."""
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()

        session_ids = {item.session_id for item in payload.samples}
        for session_id in session_ids:
            session = await self._repository.get_session_by_id(session_id)
            if session is None:
                raise SessionNotFoundException()
            if session.athlete_id != athlete.athlete_id:
                raise ForbiddenException("You may only upload HR samples for your own session.")

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

    async def get_session_hr(self, phone_number: str, athlete_id: str, session_id: UUID) -> SessionHrResponse:
        """Return aggregated, downsampled HR for `session_id`, if it belongs to the caller."""
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        if athlete.athlete_id != athlete_id:
            raise ForbiddenException("You may only read HR data for your own athlete profile.")

        session = await self._repository.get_session_by_id(session_id)
        if session is None:
            raise SessionNotFoundException()
        if session.athlete_id != athlete.athlete_id:
            raise ForbiddenException("You may only read HR data for your own session.")

        samples = await self._repository.get_samples_for_session(session_id)
        if not samples:
            return SessionHrResponse(session_id=session_id, sample_count=0)

        heart_rates = [s.heart_rate for s in samples]
        points = [
            HrPointResponse(recorded_at=s.recorded_at, heart_rate=s.heart_rate)
            for s in _downsample(samples, _MAX_CHART_POINTS)
        ]
        return SessionHrResponse(
            session_id=session_id,
            sample_count=len(samples),
            avg_hr=round(fmean(heart_rates)),
            min_hr=min(heart_rates),
            max_hr=max(heart_rates),
            points=points,
        )


def _downsample(samples: Sequence[HrSampleRecord], max_points: int) -> list[HrSampleRecord]:
    """
    Evenly stride `samples` down to at most `max_points`, preserving order
    and always including the first and last sample. Deterministic given
    the same input — no randomness, no interpolation.
    """
    n = len(samples)
    if n <= max_points:
        return list(samples)

    step = n / max_points
    indices = sorted({min(n - 1, int(i * step)) for i in range(max_points)})
    if indices[-1] != n - 1:
        indices[-1] = n - 1
    return [samples[i] for i in indices]
