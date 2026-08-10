"""Response DTOs for the psychology assessment flow."""

from pydantic import Field

from app.schemas.base import BaseSchema


class QuestionOptionResponse(BaseSchema):
    """One selectable option for a question. `score`/`weight` are deliberately never exposed to the client."""

    option_code: str = Field(..., alias="optionCode", description="The option's code.")
    option_text: str | None = Field(None, alias="optionText", description="The option's display text.")


class QuestionResponse(BaseSchema):
    """A single assessment question with its options."""

    question_number: int = Field(..., alias="questionNumber", description="The question's ordinal (1-25).")
    question_code: str | None = Field(None, alias="questionCode", description="The question's code.")
    category: str | None = Field(None, description="The question's category (e.g. \"Arousal\").")
    question_text: str | None = Field(None, alias="questionText", description="The question's display text.")
    options: list[QuestionOptionResponse] = Field(..., description="The question's selectable options.")


class AssessmentProgressResponse(BaseSchema):
    """
    Progress summary only — returned by `POST /api/v2/psychology-assessment/answers`.

    Deliberately excludes the next question: read and write responsibilities
    are kept separate, so the client always fetches the next question via
    `GET /api/v2/psychology-assessment`.
    """

    total_questions: int = Field(
        ..., alias="totalQuestions", description="Total questions in the assessment (25)."
    )
    answered_count: int = Field(
        ..., alias="answeredCount", description="How many questions have been answered."
    )
    is_complete: bool = Field(
        ..., alias="isComplete", description="Whether all questions have been answered."
    )


class AssessmentStatusResponse(AssessmentProgressResponse):
    """
    Full assessment status — returned by `GET /api/v2/psychology-assessment`.

    Serves Start, Get Progress, Get Next Question, and Resume: all four are
    the same derived read of `hamsatech.psychology_responses` against the
    25-question catalog, so they share this one response shape and this one
    endpoint.
    """

    next_question: QuestionResponse | None = Field(
        None,
        alias="nextQuestion",
        description="The next unanswered question, or null once `isComplete` is true.",
    )


class CategoryScoreResponse(BaseSchema):
    """One category's computed score, as produced by `hamsatech.calculate_psychology_scores`."""

    category: str = Field(..., description="The category's identifier (e.g. \"Arousal\").")
    display_name: str = Field(
        ..., alias="displayName", description="The category's display name (e.g. \"Steady Heart\")."
    )
    child_description: str | None = Field(
        None,
        alias="childDescription",
        description="Child-friendly description of what this category measures.",
    )
    icon_slug: str | None = Field(None, alias="iconSlug", description="Icon identifier for this category.")
    score: float | None = Field(None, description="The normalized 0-100 score for this category.")
    interpretation: str | None = Field(None, description="The interpretation banding for this score.")


class InsightResponse(BaseSchema):
    """One deterministic insight, as produced by `hamsatech.generate_deterministic_insights`."""

    category: str = Field(..., description="The category this insight applies to.")
    score: float | None = Field(None, description="The score that produced this insight.")
    title: str | None = Field(None, description="The insight's title.")
    insight_text: str | None = Field(
        None, alias="insightText", description="The insight's child-friendly message."
    )


class AssessmentCompletionResponse(BaseSchema):
    """Returned by `POST /api/v2/psychology-assessment/complete`."""

    is_complete: bool = Field(True, alias="isComplete", description="Always true on a successful completion.")
    category_scores: list[CategoryScoreResponse] = Field(
        ..., alias="categoryScores", description="Computed score per category."
    )
    insights: list[InsightResponse] = Field(..., description="Deterministic insights per category.")
