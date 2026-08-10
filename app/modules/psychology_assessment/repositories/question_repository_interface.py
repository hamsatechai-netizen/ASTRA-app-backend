"""
Psychology-question-catalog repository contract.

Backs the existing `hamsatech.psychology_questions` and
`hamsatech.psychology_question_options` tables — read-only, this module
never writes to either. Narrowly scoped to what the assessment flow needs:
the full ordered question list (to compute progress and the next
unanswered question) and one question's option set.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.models.hamsatech_psychology import HamsaTechPsychologyQuestion, HamsaTechPsychologyQuestionOption


class PsychologyQuestionRepositoryInterface(ABC):
    """Abstract contract for reading the psychology-assessment question catalog."""

    @abstractmethod
    async def get_all_ordered(self) -> Sequence[HamsaTechPsychologyQuestion]:
        """Return every question ordered by `question_number` (all 25)."""

    @abstractmethod
    async def get_options(self, question_number: int) -> Sequence[HamsaTechPsychologyQuestionOption]:
        """Return every option for `question_number`, ordered by `option_code`."""
