"""Request DTOs for the psychology assessment flow."""

from pydantic import Field

from app.schemas.base import BaseSchema


class SaveAnswerRequest(BaseSchema):
    """
    Request body for `POST /api/v2/psychology-assessment/answers`.

    Used for both a first answer and changing a previously-saved one — the
    service decides create-vs-update by checking for an existing response
    row, the same create-or-update pattern `OnboardingService` already uses
    for Steps 4-6.
    """

    question_number: int = Field(
        ..., alias="questionNumber", ge=1, description="The question being answered.", examples=[1]
    )
    option_code: str = Field(
        ..., alias="optionCode", min_length=1, description="The chosen option's code.", examples=["AR_01_A"]
    )
    answer_text: str | None = Field(
        None, alias="answerText", description="Optional free-text elaboration on the chosen option."
    )
