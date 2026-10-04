"""
Concrete psychology-question-catalog repository (SQLAlchemy), read-only
against the existing `hamsatech.psychology_questions` /
`hamsatech.psychology_question_options` tables.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_psychology import HamsaTechPsychologyQuestion, HamsaTechPsychologyQuestionOption
from app.modules.psychology_assessment.repositories.question_repository_interface import (
    PsychologyQuestionRepositoryInterface,
)


class PsychologyQuestionRepository(PsychologyQuestionRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_ordered(self) -> Sequence[HamsaTechPsychologyQuestion]:
        result = await self._session.execute(
            select(HamsaTechPsychologyQuestion).order_by(HamsaTechPsychologyQuestion.question_number)
        )
        return result.scalars().all()

    async def get_options(self, question_number: int) -> Sequence[HamsaTechPsychologyQuestionOption]:
        result = await self._session.execute(
            select(HamsaTechPsychologyQuestionOption)
            .where(HamsaTechPsychologyQuestionOption.question_number == question_number)
            .order_by(HamsaTechPsychologyQuestionOption.option_code)
        )
        return result.scalars().all()
