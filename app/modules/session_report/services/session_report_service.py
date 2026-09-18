"""
Session-report aggregation business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — same precondition every other module
in this project relies on), enforces that the caller can only read a
report for their own `athlete_id` and their own session, then reads every
table already persisted for that session — HR, score summary, series,
reflection — and assembles them into one response. Nothing is calculated
beyond simple, deterministic aggregates directly justified by stored data
(session duration, HR average/min/max/first/last, series total/average/
min/max); no Readiness/Recovery/Stress/Steady or other derived metric is
computed, since no such algorithm has been defined yet.
"""

from collections.abc import Sequence
from uuid import UUID

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.session import Session
from app.models.session_post_log import SessionPostLog
from app.models.session_series import SessionSeries
from app.models.shooting_session_log import ShootingSessionLog
from app.modules.session_report.exceptions import (
    AthleteNotFoundException,
    ForbiddenException,
    SessionNotFoundException,
)
from app.modules.session_report.repositories.session_report_repository_interface import (
    SessionReportRepositoryInterface,
)
from app.modules.session_report.schemas.responses import (
    HeartRateSummarySection,
    ReflectionSummarySection,
    ScoreSummarySection,
    SeriesEntryResponse,
    SessionReportResponse,
    SessionSummarySection,
)


class SessionReportService:
    """Resolves the authenticated athlete and session, and assembles their session report."""

    def __init__(self, repository: SessionReportRepositoryInterface) -> None:
        self._repository = repository

    async def get_session_report(
        self, phone_number: str, athlete_id: str, session_id: UUID
    ) -> SessionReportResponse:
        athlete = await self._get_athlete_or_raise(phone_number)
        if athlete.athlete_id != athlete_id:
            raise ForbiddenException("You may only read a report for your own athlete profile.")

        session = await self._repository.get_session_by_id(session_id)
        if session is None:
            raise SessionNotFoundException()
        if session.athlete_id != athlete.athlete_id:
            raise ForbiddenException("You may only read a report for your own session.")

        hr_aggregate = await self._repository.get_hr_aggregate_for_session(session_id)
        score_row = await self._repository.get_score_for_session(session_id)
        series_rows = await self._repository.get_series_for_session(session_id)
        reflection_row = await self._repository.get_reflection_for_session(session_id)

        return SessionReportResponse(
            session_id=session.session_id,
            athlete_id=session.athlete_id,
            session_status="completed" if session.end_time is not None else "in_progress",
            session_summary=_build_session_summary(session),
            heart_rate=HeartRateSummarySection(
                sample_count=hr_aggregate.sample_count,
                average_heart_rate=hr_aggregate.avg_hr,
                minimum_heart_rate=hr_aggregate.min_hr,
                maximum_heart_rate=hr_aggregate.max_hr,
                first_heart_rate=hr_aggregate.first_hr,
                last_heart_rate=hr_aggregate.last_hr,
            ),
            scores=_build_scores(score_row, series_rows),
            series=[
                SeriesEntryResponse(
                    series_number=row.series_number,
                    total_score=row.total_score,
                    shots_fired=row.shots_fired,
                )
                for row in series_rows
            ],
            reflection=_build_reflection(reflection_row),
        )

    async def _get_athlete_or_raise(self, phone_number: str) -> HamsaTechAthlete:
        athlete = await self._repository.get_athlete_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        return athlete


def _build_session_summary(session: Session) -> SessionSummarySection:
    duration_seconds = None
    if session.end_time is not None:
        duration_seconds = int((session.end_time - session.start_time).total_seconds())

    return SessionSummarySection(
        session_type=session.session_type,
        started_at=session.start_time,
        completed_at=session.end_time,
        duration_seconds=duration_seconds,
    )


def _build_scores(
    score_row: ShootingSessionLog | None, series_rows: Sequence[SessionSeries]
) -> ScoreSummarySection | None:
    if score_row is None and not series_rows:
        return None

    series_totals = [row.total_score for row in series_rows if row.total_score is not None]

    return ScoreSummarySection(
        total_shots=score_row.total_shots if score_row is not None else None,
        avg_score=score_row.avg_score if score_row is not None else None,
        best_series_score=score_row.best_series_score if score_row is not None else None,
        total_score=sum(series_totals) if series_totals else None,
        average_score=(sum(series_totals) / len(series_totals)) if series_totals else None,
        minimum_score=min(series_totals) if series_totals else None,
        maximum_score=max(series_totals) if series_totals else None,
    )


def _build_reflection(reflection_row: SessionPostLog | None) -> ReflectionSummarySection | None:
    if reflection_row is None:
        return None

    return ReflectionSummarySection(
        mood=reflection_row.mood,
        what_worked=reflection_row.what_worked,
        what_didnt=reflection_row.what_didnt,
    )
