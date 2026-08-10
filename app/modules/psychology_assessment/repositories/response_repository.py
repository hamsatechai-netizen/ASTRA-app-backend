"""
Concrete psychology-response repository (SQLAlchemy) against the existing
`hamsatech.athletes` and `hamsatech.psychology_responses` tables. Only ever
flushes, never commits — the request-scoped `AsyncSession` from
`app.dependencies.database.get_db` owns the transaction boundary.

`acquire_answer_lock` takes a transaction-scoped Postgres advisory lock,
same `pg_advisory_xact_lock(hashtext(:key))` pattern as
`AthleteProfileRepository._generate_next_athlete_id`, but keyed per
`(athlete_id, question_number)` rather than globally — only two requests
racing to save the *same* athlete's *same* question ever contend. The
lock is released automatically at commit or rollback (i.e. when
`get_db()` finishes the request); no schema change or unique constraint
is involved.
"""

from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_psychology import HamsaTechPsychologyResponse
from app.modules.psychology_assessment.repositories.response_repository_interface import (
    PsychologyResponseRepositoryInterface,
)


class PsychologyResponseRepository(PsychologyResponseRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        result = await self._session.execute(
            select(HamsaTechAthlete).where(HamsaTechAthlete.contact_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def acquire_answer_lock(self, athlete_id: str, question_number: int) -> None:
        lock_key = f"hamsatech.psychology_responses:{athlete_id}:{question_number}"
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": lock_key}
        )

    async def get_answered_question_numbers(self, athlete_id: str) -> set[int]:
        result = await self._session.execute(
            select(HamsaTechPsychologyResponse.question_id).where(
                HamsaTechPsychologyResponse.athlete_id == athlete_id
            )
        )
        return {question_id for question_id in result.scalars().all() if question_id is not None}

    async def get_by_athlete_and_question(
        self, athlete_id: str, question_number: int
    ) -> HamsaTechPsychologyResponse | None:
        result = await self._session.execute(
            select(HamsaTechPsychologyResponse).where(
                HamsaTechPsychologyResponse.athlete_id == athlete_id,
                HamsaTechPsychologyResponse.question_id == question_number,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, athlete_id: str, question_number: int, option_code: str, answer_text: str | None
    ) -> HamsaTechPsychologyResponse:
        response = HamsaTechPsychologyResponse(
            athlete_id=athlete_id,
            question_id=question_number,
            chosen_option=option_code,
            answer_text=answer_text,
        )
        self._session.add(response)
        await self._session.flush()
        return response

    async def update(
        self, response: HamsaTechPsychologyResponse, option_code: str, answer_text: str | None
    ) -> HamsaTechPsychologyResponse:
        response.chosen_option = option_code
        response.answer_text = answer_text
        await self._session.flush()
        return response

    async def get_all_for_athlete(self, athlete_id: str) -> Sequence[HamsaTechPsychologyResponse]:
        result = await self._session.execute(
            select(HamsaTechPsychologyResponse).where(HamsaTechPsychologyResponse.athlete_id == athlete_id)
        )
        return result.scalars().all()
