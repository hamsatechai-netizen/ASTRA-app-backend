"""Shared pagination query-parameter dependency, reused by any future list endpoint."""

from dataclasses import dataclass

from fastapi import Query

from app.constants.api import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


@dataclass(frozen=True)
class PaginationParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def get_pagination_params(
    page: int = Query(DEFAULT_PAGE, ge=1, description="1-indexed page number"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)
