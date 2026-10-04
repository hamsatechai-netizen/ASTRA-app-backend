"""
Psychology-scoring repository contract.

Wraps the two existing `hamsatech` SQL functions —
`calculate_psychology_scores(text)` and `generate_deterministic_insights(text)`
— plus read access to the tables they populate
(`hamsatech.psychology_scores`, `hamsatech.category_definitions`,
`hamsatech.ai_insights`). Deliberately calls the functions rather than
reimplementing their weighting/interpretation logic in Python, per the
approved design: this project reuses the existing, already-correct
scoring math instead of duplicating it.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.models.hamsatech_psychology import (
    HamsaTechAiInsight,
    HamsaTechCategoryDefinition,
    HamsaTechPsychologyScore,
)


class PsychologyScoringRepositoryInterface(ABC):
    """Abstract contract for invoking and reading back the existing psychology-scoring SQL functions."""

    @abstractmethod
    async def calculate_scores(self, athlete_id: str) -> None:
        """Call `hamsatech.calculate_psychology_scores(athlete_id)`, refreshing `psychology_scores`."""

    @abstractmethod
    async def generate_insights(self, athlete_id: str) -> None:
        """Call `hamsatech.generate_deterministic_insights(athlete_id)`, refreshing `ai_insights`."""

    @abstractmethod
    async def get_scores_with_categories(
        self, athlete_id: str
    ) -> Sequence[tuple[HamsaTechPsychologyScore, HamsaTechCategoryDefinition]]:
        """Return `athlete_id`'s scores joined with their category display metadata."""

    @abstractmethod
    async def get_insights(self, athlete_id: str) -> Sequence[HamsaTechAiInsight]:
        """Return `athlete_id`'s insight rows."""
