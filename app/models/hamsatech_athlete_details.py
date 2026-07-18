"""
ORM mapping onto the existing `hamsatech.athlete_details` table — a
partial projection covering only Onboarding Step 4 (Academic Profile):
`class`, `school_name`, `academic_performance`. The real table also
carries diet/sleep/psychology columns (`diet_type`, `sleep_time`,
`anger_pattern`, `athlete_goal`, etc.) that belong to other, not-yet-
implemented onboarding steps and are intentionally not mapped here —
omitting them from the ORM means they're simply absent from any
INSERT/UPDATE this model issues, never touched or overwritten.

`athlete_id` is a UNIQUE + FOREIGN KEY column referencing
`hamsatech.athletes.athlete_id` (one details row per athlete, confirmed
via inspection — no separate surrogate primary key exists on the real
table), so it is declared as the ORM primary key here too.

`class` is a Python reserved word, so the mapped attribute is named
`class_`, explicitly bound to the real `class` column name via
`mapped_column("class", ...)`.

Uses `ExternalBase`, not `Base`: this project never creates, alters, or
migrates this table.
"""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class HamsaTechAthleteDetails(ExternalBase):
    """Partial mapping onto the existing `hamsatech.athlete_details` table."""

    __tablename__ = "athlete_details"
    __table_args__ = {"schema": "hamsatech"}

    athlete_id: Mapped[str] = mapped_column(Text, primary_key=True)
    class_: Mapped[str | None] = mapped_column("class", Text, nullable=True)
    school_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    academic_performance: Mapped[str | None] = mapped_column(Text, nullable=True)
