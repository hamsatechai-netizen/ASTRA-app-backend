"""Academies module schemas — re-exported here for a single, stable import path."""

from app.common.responses import ErrorResponse
from app.modules.academies.schemas.responses import AcademyResponse

__all__ = ["AcademyResponse", "ErrorResponse"]
