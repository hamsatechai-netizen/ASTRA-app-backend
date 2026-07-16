"""Generic enumerations shared by multiple layers (not tied to any single domain)."""

from enum import StrEnum


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
