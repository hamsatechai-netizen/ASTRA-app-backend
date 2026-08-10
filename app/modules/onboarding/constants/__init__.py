"""
Onboarding module constants.

`Gender` values are kept to exactly what the existing `hamsatech.athletes`
data uses (confirmed by inspecting the real column: only "Male"/"Female"
values are present) rather than inventing options the source system
doesn't have.
"""

from enum import StrEnum


class Gender(StrEnum):
    MALE = "Male"
    FEMALE = "Female"
