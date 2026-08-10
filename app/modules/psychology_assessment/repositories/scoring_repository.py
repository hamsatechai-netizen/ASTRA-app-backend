"""
Concrete psychology-scoring repository (SQLAlchemy) against the existing
`hamsatech` psychology-scoring SQL functions and tables. Only ever flushes
implicitly via `execute`, never commits — the request-scoped `AsyncSession`
from `app.dependencies.database.get_db` owns the transaction boundary, so
a failure after `calculate_scores` but before the request completes rolls
back the function's own `DELETE`+`INSERT` along with everything else.

Calls `hamsatech.calculate_psychology_scores(text)` explicitly — the
`(uuid)` overload of the same function name is dead legacy code (it
references a nonexistent `hamsatech.psychology_answers` table and a
nonexistent `psychology_questions.id` column, confirmed via inspection)
and must never be invoked.
"""

from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hamsatech_psychology import (
    HamsaTechAiInsight,
    HamsaTechCategoryDefinition,
    HamsaTechPsychologyScore,
)
from app.modules.psychology_assessment.repositories.scoring_repository_interface import (
    PsychologyScoringRepositoryInterface,
)


class PsychologyScoringRepository(PsychologyScoringRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def calculate_scores(self, athlete_id: str) -> None:
        await self._session.execute(
            text("SELECT hamsatech.calculate_psychology_scores(CAST(:athlete_id AS text))"),
            {"athlete_id": athlete_id},
        )

    async def generate_insights(self, athlete_id: str) -> None:
        await self._session.execute(
            text("SELECT hamsatech.generate_deterministic_insights(:athlete_id)"),
            {"athlete_id": athlete_id},
        )

    async def get_scores_with_categories(
        self, athlete_id: str
    ) -> Sequence[tuple[HamsaTechPsychologyScore, HamsaTechCategoryDefinition]]:
        result = await self._session.execute(
            select(HamsaTechPsychologyScore, HamsaTechCategoryDefinition)
            .join(
                HamsaTechCategoryDefinition,
                HamsaTechPsychologyScore.category == HamsaTechCategoryDefinition.category_id,
            )
            .where(HamsaTechPsychologyScore.athlete_id == athlete_id)
            .order_by(HamsaTechCategoryDefinition.category_id)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def get_insights(self, athlete_id: str) -> Sequence[HamsaTechAiInsight]:
        result = await self._session.execute(
            select(HamsaTechAiInsight)
            .where(HamsaTechAiInsight.athlete_id == athlete_id)
            .order_by(HamsaTechAiInsight.category)
        )
        return result.scalars().all()
