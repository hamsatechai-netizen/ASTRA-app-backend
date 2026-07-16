"""
Standard API response envelopes.

Every endpoint (present and future) responds with one of these shapes so
API consumers can rely on a single, predictable contract:

- `SuccessResponse[T]`    — single-resource / action responses.
- `PaginatedResponse[T]`  — list responses with pagination metadata.
- `ErrorResponse`         — all error responses (see `app.exceptions`).
"""

from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=_utc_now)


class SuccessResponse(BaseModel, Generic[DataT]):
    success: bool = True
    data: DataT
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=_utc_now)


class PaginationMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[DataT]):
    success: bool = True
    data: list[DataT]
    meta: PaginationMeta
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=_utc_now)
