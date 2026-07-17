"""
ORM mapping onto the existing `hamsatech.users` table.

This table pre-dates this codebase and is shared with other systems — its
39 existing rows were not created by anything here (confirmed by
inspecting the entire backend for any prior reference before mapping it).
Uses `ExternalBase`, not `Base`: this project never creates, alters, or
migrates this table — see `app.database.external_base` for why that's a
separate registry rather than just a convention to remember.

Column types intentionally match what already exists rather than this
project's own conventions — notably `phone_verified_at`/`created_at`/
`last_login_at` are `timestamp without time zone` (naive) in the real
table, not the timezone-aware columns this project's own models use.

`role` and `created_at` declare `server_default` to match the real
column defaults (`'athlete'` and `now()` respectively, confirmed via
direct inspection) — this is metadata only, it issues no DDL, but it's
required for SQLAlchemy to *omit* these columns from the INSERT when
unset in Python rather than sending an explicit `NULL` that would
override the database's own default. (Verified this the hard way: an
initial version without `server_default` silently inserted `NULL` for
both instead of letting the real defaults apply.)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.external_base import ExternalBase


class HamsaTechUser(ExternalBase):
    """Phone-verified identity record — the reused authentication table for Phase 3."""

    __tablename__ = "users"
    __table_args__ = {"schema": "hamsatech"}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uid: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    role: Mapped[str | None] = mapped_column(Text, nullable=True, server_default=text("'athlete'"))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=text("now()")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
