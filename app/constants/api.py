"""
API-related constants.

Kept separate from `config.settings` because these are fixed contract
values (part of the API surface), not deployment-tunable configuration.
"""

from enum import StrEnum


class APIVersion(StrEnum):
    V1 = "v1"


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

REQUEST_ID_HEADER = "X-Request-ID"
