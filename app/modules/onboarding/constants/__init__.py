"""
Onboarding module constants.

`Gender` values are kept to exactly what the existing `hamsatech.athletes`
data uses (confirmed by inspecting the real column: only "Male"/"Female"
values are present) rather than inventing options the source system
doesn't have.
"""

from enum import StrEnum
from typing import Final

TOTAL_ONBOARDING_STEPS: Final[int] = 6  # Screens 1-6 of the onboarding UI; only Step 1 is implemented so far.


class Gender(StrEnum):
    MALE = "Male"
    FEMALE = "Female"
