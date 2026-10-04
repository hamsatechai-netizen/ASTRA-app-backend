"""
ORM mappings onto the existing `hamsatech` psychology-assessment tables —
`psychology_questions`, `psychology_question_options`, `psychology_responses`,
`psychology_scores`, `category_definitions`, and `ai_insights`. Confirmed via
direct inspection: 25 rows in `psychology_questions` (5 categories x 5
questions), 100 rows in `psychology_question_options` (4 per question), and
existing `athlete_id`-keyed rows in `psychology_responses`/`psychology_scores`.

Grouped in one file, unlike `hamsatech_athlete.py`/`hamsatech_academy.py`
(each their own file): those tables are shared across the auth, onboarding,
and academies modules, while these six tables are read/written exclusively
by `app.modules.psychology_assessment`.

Uses `ExternalBase`, not `Base`: this project never creates, alters, or
migrates any of these tables. `psychology_scores` and `ai_insights` are
never written to directly from Python — they are populated by the existing
`hamsatech.calculate_psychology_scores` / `hamsatech.generate_deterministic_insights`
SQL functions (called via the scoring repository) and only ever read back
here.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Float, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class HamsaTechPsychologyQuestion(ExternalBase):
    """Partial mapping onto `hamsatech.psychology_questions` (25 rows, one per assessment question)."""

    __tablename__ = "psychology_questions"
    __table_args__ = {"schema": "hamsatech"}

    question_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)


class HamsaTechPsychologyQuestionOption(ExternalBase):
    """
    Partial mapping onto `hamsatech.psychology_question_options` (100 rows,
    4 per question). The real table has no primary key or unique constraint
    (confirmed via inspection) — `option_code` uniqueness per question is a
    convention only, so the service layer validates membership explicitly
    rather than relying on the database to reject an invalid code.
    """

    __tablename__ = "psychology_question_options"
    __table_args__ = {"schema": "hamsatech"}

    # No real primary key exists on this table; `option_code` is declared
    # the ORM primary key (unique in practice) purely so SQLAlchemy's
    # identity map has something to key rows on for read-only queries.
    option_code: Mapped[str] = mapped_column(Text, primary_key=True)
    option_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_number: Mapped[int | None] = mapped_column(Integer, nullable=True)


class HamsaTechPsychologyResponse(ExternalBase):
    """
    Partial mapping onto `hamsatech.psychology_responses` — one row per
    saved answer. `id` is a server-generated serial primary key (never set
    from Python). No unique constraint exists on `(athlete_id, question_id)`
    (confirmed via inspection), so the repository never blindly inserts —
    the service checks for an existing row first and updates it in place.
    """

    __tablename__ = "psychology_responses"
    __table_args__ = {"schema": "hamsatech"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chosen_option: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class HamsaTechPsychologyScore(ExternalBase):
    """
    Read-only mapping onto `hamsatech.psychology_scores`. Rows here are
    produced exclusively by `hamsatech.calculate_psychology_scores(text)`
    (called via `PsychologyScoringRepository`) — this project never inserts
    or updates this table directly.
    """

    __tablename__ = "psychology_scores"
    __table_args__ = {"schema": "hamsatech"}

    score_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    athlete_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    calculation_logic: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(nullable=True)


class HamsaTechCategoryDefinition(ExternalBase):
    """Partial mapping onto `hamsatech.category_definitions` (5 rows, one per assessment category)."""

    __tablename__ = "category_definitions"
    __table_args__ = {"schema": "hamsatech"}

    category_id: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    child_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_slug: Mapped[str | None] = mapped_column(Text, nullable=True)


class HamsaTechAiInsight(ExternalBase):
    """
    Read-only mapping onto `hamsatech.ai_insights`. Rows here are produced
    exclusively by `hamsatech.generate_deterministic_insights(text)` (called
    via `PsychologyScoringRepository`) — this project never inserts or
    updates this table directly. The real table has no single-column
    primary key suited to the ORM identity map, so `athlete_id` + `category`
    together are declared as a composite primary key, matching how each
    athlete has at most one insight row per category.
    """

    __tablename__ = "ai_insights"
    __table_args__ = {"schema": "hamsatech"}

    athlete_id: Mapped[str] = mapped_column(Text, primary_key=True)
    category: Mapped[str] = mapped_column(Text, primary_key=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    insight_text: Mapped[str | None] = mapped_column(Text, nullable=True)
