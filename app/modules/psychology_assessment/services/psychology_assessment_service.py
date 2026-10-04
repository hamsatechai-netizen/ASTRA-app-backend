"""
Psychology assessment business logic.

Resolves the authenticated athlete's existing `hamsatech.athletes` row by
contact number (never creates one — that already happens during Verify
OTP, same precondition `OnboardingService` relies on) and derives every
piece of status entirely from `hamsatech.psychology_responses` against the
25-question catalog: no session/attempt/progress table exists or is
introduced. Duplicate-answer prevention (update instead of a second insert)
and option-code validation both happen here, in the service layer, because
the underlying `hamsatech.psychology_responses` /
`hamsatech.psychology_question_options` tables enforce neither at the
database level. `save_answer` additionally takes a per-athlete/question
Postgres advisory lock (via `PsychologyResponseRepositoryInterface
.acquire_answer_lock`) before its check-then-act read/write, closing the
race window a fast double-submit (e.g. double-tapping "Next") could
otherwise hit — same pattern `AthleteProfileRepository` already uses for
athlete-ID generation. Scoring math itself is never reimplemented here —
`complete` only ever delegates to the existing
`hamsatech.calculate_psychology_scores` /
`hamsatech.generate_deterministic_insights` SQL functions via
`PsychologyScoringRepositoryInterface`.
"""

from collections.abc import Sequence

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_psychology import HamsaTechPsychologyQuestion
from app.modules.psychology_assessment.exceptions import (
    AssessmentIncompleteException,
    AthleteNotFoundException,
    InvalidOptionException,
    InvalidQuestionException,
)
from app.modules.psychology_assessment.repositories.question_repository_interface import (
    PsychologyQuestionRepositoryInterface,
)
from app.modules.psychology_assessment.repositories.response_repository_interface import (
    PsychologyResponseRepositoryInterface,
)
from app.modules.psychology_assessment.repositories.scoring_repository_interface import (
    PsychologyScoringRepositoryInterface,
)
from app.modules.psychology_assessment.schemas.requests import SaveAnswerRequest
from app.modules.psychology_assessment.schemas.responses import (
    AssessmentCompletionResponse,
    AssessmentProgressResponse,
    AssessmentStatusResponse,
    CategoryScoreResponse,
    InsightResponse,
    QuestionOptionResponse,
    QuestionResponse,
)


class PsychologyAssessmentService:
    """Resolves assessment status, saves/updates answers, and completes + scores the assessment."""

    def __init__(
        self,
        question_repository: PsychologyQuestionRepositoryInterface,
        response_repository: PsychologyResponseRepositoryInterface,
        scoring_repository: PsychologyScoringRepositoryInterface,
    ) -> None:
        self._question_repository = question_repository
        self._response_repository = response_repository
        self._scoring_repository = scoring_repository

    async def get_status(self, phone_number: str) -> AssessmentStatusResponse:
        """Return full assessment status (progress + next unanswered question) for `phone_number`."""
        athlete = await self._get_athlete_or_raise(phone_number)

        questions = await self._question_repository.get_all_ordered()
        answered = await self._response_repository.get_answered_question_numbers(athlete.athlete_id)

        next_question = await self._build_next_question(questions, answered)

        return AssessmentStatusResponse(
            total_questions=len(questions),
            answered_count=len(answered),
            is_complete=len(answered) >= len(questions),
            next_question=next_question,
        )

    async def save_answer(self, phone_number: str, payload: SaveAnswerRequest) -> AssessmentProgressResponse:
        """
        Save or update `payload`'s answer for the athlete matching
        `phone_number`, then return updated progress only (no next
        question — the client fetches that via `get_status`).
        """
        athlete = await self._get_athlete_or_raise(phone_number)

        options = await self._question_repository.get_options(payload.question_number)
        if not options:
            raise InvalidQuestionException()

        valid_option_codes = {option.option_code for option in options}
        if payload.option_code not in valid_option_codes:
            raise InvalidOptionException()

        # Held for the rest of this transaction (released at commit/rollback
        # in `get_db()`), so a concurrent request for the same
        # athlete/question blocks here until this one finishes, then
        # correctly observes the row this request just wrote.
        await self._response_repository.acquire_answer_lock(athlete.athlete_id, payload.question_number)

        existing = await self._response_repository.get_by_athlete_and_question(
            athlete.athlete_id, payload.question_number
        )
        if existing is None:
            await self._response_repository.create(
                athlete.athlete_id, payload.question_number, payload.option_code, payload.answer_text
            )
        else:
            await self._response_repository.update(existing, payload.option_code, payload.answer_text)

        questions = await self._question_repository.get_all_ordered()
        answered = await self._response_repository.get_answered_question_numbers(athlete.athlete_id)
        return AssessmentProgressResponse(
            total_questions=len(questions),
            answered_count=len(answered),
            is_complete=len(answered) >= len(questions),
        )

    async def complete(self, phone_number: str) -> AssessmentCompletionResponse:
        """
        Score and complete the assessment for the athlete matching
        `phone_number`. Raises `AssessmentIncompleteException` unless all
        questions have been answered.
        """
        athlete = await self._get_athlete_or_raise(phone_number)

        questions = await self._question_repository.get_all_ordered()
        answered = await self._response_repository.get_answered_question_numbers(athlete.athlete_id)
        if len(answered) < len(questions):
            raise AssessmentIncompleteException(
                details={"answeredCount": len(answered), "totalQuestions": len(questions)}
            )

        await self._scoring_repository.calculate_scores(athlete.athlete_id)
        await self._scoring_repository.generate_insights(athlete.athlete_id)

        scores = await self._scoring_repository.get_scores_with_categories(athlete.athlete_id)
        insights = await self._scoring_repository.get_insights(athlete.athlete_id)

        return AssessmentCompletionResponse(
            is_complete=True,
            category_scores=[
                CategoryScoreResponse(
                    category=score.category,
                    display_name=category.display_name,
                    child_description=category.child_description,
                    icon_slug=category.icon_slug,
                    score=score.score,
                    interpretation=score.interpretation,
                )
                for score, category in scores
            ],
            insights=[
                InsightResponse(
                    category=insight.category,
                    score=insight.score,
                    title=insight.title,
                    insight_text=insight.insight_text,
                )
                for insight in insights
            ],
        )

    async def _get_athlete_or_raise(self, phone_number: str) -> HamsaTechAthlete:
        athlete = await self._response_repository.get_by_contact_number(phone_number)
        if athlete is None:
            raise AthleteNotFoundException()
        return athlete

    async def _build_next_question(
        self, questions: Sequence[HamsaTechPsychologyQuestion], answered: set[int]
    ) -> QuestionResponse | None:
        next_question = next((q for q in questions if q.question_number not in answered), None)
        if next_question is None:
            return None

        options = await self._question_repository.get_options(next_question.question_number)
        return QuestionResponse(
            question_number=next_question.question_number,
            question_code=next_question.question_code,
            category=next_question.category,
            question_text=next_question.question_text,
            options=[
                QuestionOptionResponse(option_code=option.option_code, option_text=option.option_text)
                for option in options
            ],
        )
