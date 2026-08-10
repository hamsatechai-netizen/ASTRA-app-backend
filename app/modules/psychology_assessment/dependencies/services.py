"""
Service/repository construction for FastAPI's DI system.

Mirrors `app.modules.onboarding.dependencies.services` — each function is a
`Depends()`-compatible provider, chained so the router ends up with a
fully-wired `PsychologyAssessmentService` per request without constructing
anything itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.psychology_assessment.repositories.question_repository import PsychologyQuestionRepository
from app.modules.psychology_assessment.repositories.question_repository_interface import (
    PsychologyQuestionRepositoryInterface,
)
from app.modules.psychology_assessment.repositories.response_repository import PsychologyResponseRepository
from app.modules.psychology_assessment.repositories.response_repository_interface import (
    PsychologyResponseRepositoryInterface,
)
from app.modules.psychology_assessment.repositories.scoring_repository import PsychologyScoringRepository
from app.modules.psychology_assessment.repositories.scoring_repository_interface import (
    PsychologyScoringRepositoryInterface,
)
from app.modules.psychology_assessment.services.psychology_assessment_service import (
    PsychologyAssessmentService,
)


def get_psychology_question_repository(
    session: AsyncSession = Depends(get_db),
) -> PsychologyQuestionRepositoryInterface:
    return PsychologyQuestionRepository(session)


def get_psychology_response_repository(
    session: AsyncSession = Depends(get_db),
) -> PsychologyResponseRepositoryInterface:
    return PsychologyResponseRepository(session)


def get_psychology_scoring_repository(
    session: AsyncSession = Depends(get_db),
) -> PsychologyScoringRepositoryInterface:
    return PsychologyScoringRepository(session)


def get_psychology_assessment_service(
    question_repository: PsychologyQuestionRepositoryInterface = Depends(get_psychology_question_repository),
    response_repository: PsychologyResponseRepositoryInterface = Depends(get_psychology_response_repository),
    scoring_repository: PsychologyScoringRepositoryInterface = Depends(get_psychology_scoring_repository),
) -> PsychologyAssessmentService:
    return PsychologyAssessmentService(question_repository, response_repository, scoring_repository)
