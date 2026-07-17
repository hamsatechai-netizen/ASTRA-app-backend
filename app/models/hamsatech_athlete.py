"""
ORM mapping onto the existing `hamsatech.athletes` table — minimal
projection only. The real table has 17 columns (physical attributes,
academy/coach assignment, etc.) owned entirely by other systems; this
backend only needs `athlete_id` (to create a row) and `contact_number`
(to check/establish the link to a phone-verified identity), so only those
two are mapped. Uses `ExternalBase` — see `app.database.external_base`
and `app.models.hamsatech_user` for why.
"""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class HamsaTechAthlete(ExternalBase):
    """Minimal mapping onto the existing `hamsatech.athletes` sports-profile table."""

    __tablename__ = "athletes"
    __table_args__ = {"schema": "hamsatech"}

    athlete_id: Mapped[str] = mapped_column(Text, primary_key=True)
    contact_number: Mapped[str | None] = mapped_column(Text, nullable=True)
