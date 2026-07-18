"""
ORM mapping onto the existing `hamsatech.athletes` table — a partial
projection, not the full 17+ column table. The real table has columns
(physical attributes, academy/coach assignment, etc.) owned entirely by
other systems and not mapped here; this file maps `athlete_id` (to
create a row) and `contact_number` (to check/establish the link to a
phone-verified identity), the 3 pre-existing columns Onboarding Step 1
needs (`athlete_name`, `date_of_birth`, `gender`), and the 8 onboarding
columns added by `migrations/versions/0002_add_onboarding_columns.py`.
Uses `ExternalBase` — see `app.database.external_base` and
`app.models.hamsatech_user` for why.
"""

from datetime import date

from sqlalchemy import ARRAY, Date, Integer, Numeric, SmallInteger, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class HamsaTechAthlete(ExternalBase):
    """Partial mapping onto the existing `hamsatech.athletes` sports-profile table."""

    __tablename__ = "athletes"
    __table_args__ = {"schema": "hamsatech"}

    athlete_id: Mapped[str] = mapped_column(Text, primary_key=True)
    contact_number: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Pre-existing columns needed for Onboarding Step 1 ---
    athlete_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Onboarding columns (added by 0002_add_onboarding_columns) ---
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    years_shooting: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_practice_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    target_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    performance_blockers: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    goal_30_day: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal_6_month: Mapped[str | None] = mapped_column(Text, nullable=True)
    # `server_default` matches the real column's `DEFAULT 1` (see the
    # migration) so a row created via `AthleteProfileRepository.create_minimal`
    # — which never sets this column explicitly — gets 1 from the database
    # instead of SQLAlchemy sending an explicit NULL over it (the same class
    # of bug fixed earlier for `HamsaTechUser.role`/`created_at`).
    current_onboarding_step: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, server_default=text("1")
    )
