"""
Psychology assessment router.

Every endpoint requires an authenticated athlete (`get_current_athlete`)
and delegates entirely to `PsychologyAssessmentService`, which reads/writes
the existing `hamsatech.psychology_responses` row(s) matched by the
authenticated identity's phone number. Mounted under
`/api/v2/psychology-assessment` via `app/api/v2/router.py`.

Three endpoints cover the eight original use-cases (Start, Get Progress,
Get Next Question, Save Answer, Update Answer, Resume, Complete — "Skip"
has no server-side route, it's a Flutter-only navigation action): `GET`
serves Start/Progress/Next-Question/Resume as one derived read, `POST
/answers` is a single save-or-update endpoint, `POST /complete` scores and
finalizes.
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies.current_athlete import get_current_athlete
from app.modules.auth.schemas.identity import AuthenticatedIdentity
from app.modules.psychology_assessment.dependencies.services import get_psychology_assessment_service
from app.modules.psychology_assessment.schemas import (
    AssessmentCompletionResponse,
    AssessmentProgressResponse,
    AssessmentStatusResponse,
    ErrorResponse,
    SaveAnswerRequest,
)
from app.modules.psychology_assessment.services.psychology_assessment_service import (
    PsychologyAssessmentService,
)

router = APIRouter()

_BASE_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "Missing, invalid, or expired access token.",
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "No athlete profile exists for the authenticated account.",
    },
}

_SAVE_ANSWER_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_BASE_RESPONSES,
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "The question does not exist, or the option is not valid for it.",
    },
}

_COMPLETE_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_BASE_RESPONSES,
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "Not all 25 questions have been answered yet.",
    },
}


@router.get(
    "",
    response_model=AssessmentStatusResponse,
    responses=_BASE_RESPONSES,
    summary="Get the authenticated athlete's psychology assessment status",
    description=(
        "Returns total/answered question counts, completion status, and the "
        "next unanswered question (or null once complete) for the "
        "authenticated athlete. Serves Start, Get Progress, Get Next "
        "Question, and Resume — all four are the same derived read of "
        "`hamsatech.psychology_responses`."
    ),
    tags=["Psychology Assessment"],
)
async def get_assessment_status(
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    assessment_service: PsychologyAssessmentService = Depends(get_psychology_assessment_service),
) -> AssessmentStatusResponse:
    """Return the current assessment status for the authenticated athlete."""
    return await assessment_service.get_status(identity.phone_number)


@router.post(
    "/answers",
    response_model=AssessmentProgressResponse,
    responses=_SAVE_ANSWER_RESPONSES,
    summary="Save or update an answer",
    description=(
        "Saves the given option as the athlete's answer to `questionNumber`, "
        "updating it in place if already answered. Returns updated progress "
        "only (`totalQuestions`, `answeredCount`, `isComplete`) — fetch the "
        "next question via `GET /api/v2/psychology-assessment`."
    ),
    tags=["Psychology Assessment"],
)
async def save_answer(
    payload: SaveAnswerRequest,
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    assessment_service: PsychologyAssessmentService = Depends(get_psychology_assessment_service),
) -> AssessmentProgressResponse:
    """Save or update `payload` as an answer for the authenticated athlete."""
    return await assessment_service.save_answer(identity.phone_number, payload)


@router.post(
    "/complete",
    response_model=AssessmentCompletionResponse,
    responses=_COMPLETE_RESPONSES,
    summary="Complete and score the psychology assessment",
    description=(
        "Requires all 25 questions to already be answered. Invokes the "
        "existing `hamsatech.calculate_psychology_scores` and "
        "`hamsatech.generate_deterministic_insights` SQL functions and "
        "returns the resulting per-category scores and insights."
    ),
    tags=["Psychology Assessment"],
)
async def complete_assessment(
    identity: AuthenticatedIdentity = Depends(get_current_athlete),
    assessment_service: PsychologyAssessmentService = Depends(get_psychology_assessment_service),
) -> AssessmentCompletionResponse:
    """Score and complete the assessment for the authenticated athlete."""
    return await assessment_service.complete(identity.phone_number)
