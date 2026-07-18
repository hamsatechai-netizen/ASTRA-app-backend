"""Onboarding module schemas — re-exported here for a single, stable import path."""

from app.common.responses import ErrorResponse
from app.modules.onboarding.schemas.requests import OnboardingStep1Request
from app.modules.onboarding.schemas.responses import OnboardingStatusResponse

__all__ = [
    "OnboardingStep1Request",
    "OnboardingStatusResponse",
    "ErrorResponse",
]
