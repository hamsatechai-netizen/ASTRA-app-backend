"""
ORM mapping onto the existing `hamsatech.academies` table — a partial
projection: `academy_id`, `academy_name`, `location`. The real table also
carries `created_at`, `updated_at`, `last_updated_at`, `updated_by`,
`academy_id_text`, and `branch_name` (confirmed via inspection), none of
which the academy-selection list needs, so they are intentionally not
mapped here.

There is no `is_active`/soft-delete column on the real table — every row
present is therefore returned by the repository; there is nothing to
filter by.

Uses `ExternalBase`, not `Base`: this project never creates, alters, or
migrates this table.
"""

import uuid

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class HamsaTechAcademy(ExternalBase):
    """Partial mapping onto the existing `hamsatech.academies` table."""

    __tablename__ = "academies"
    __table_args__ = {"schema": "hamsatech"}

    academy_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    academy_name: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
