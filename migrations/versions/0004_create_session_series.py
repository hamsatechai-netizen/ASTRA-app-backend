"""create hamsatech.session_series

Revision ID: 0004_create_session_series
Revises: 0003_add_reflection_columns
Create Date: 2026-08-18

Unlike `0002_add_onboarding_columns` / `0003_add_reflection_columns` (which
alter existing externally-owned tables), this migration creates a brand
new table in the `hamsatech` schema — a further, explicitly-approved
exception to "this project doesn't own the `hamsatech` schema", made
because no existing table stores per-series data (confirmed by a full
read-only audit of every table/column in `hamsatech` before this
migration was written — see the series-persistence investigation).
Session-level aggregates already live in `hamsatech.shooting_session_log`
(untouched by this migration); this table is strictly per-series.

Hand-written and executed via raw SQL (not Alembic's `op.create_table`),
matching the established pattern for every other `hamsatech.*` migration
in this project: the table is mapped with `ExternalBase`
(`app/models/session_series.py`), deliberately excluded from
`target_metadata`, so autogenerate can never propose further changes to
it — any future change must be another reviewed, hand-written migration.

`(session_id, series_number)` is the natural key a series is uniquely
identified by (matches the Flutter client's own semantics: one call per
1-indexed series number, safely resubmittable) — enforced with a UNIQUE
constraint. `id` is a separate synthetic primary key, matching the same
`id` + separate UNIQUE-on-natural-key shape already used by
`hamsatech.session_post_log` / `hamsatech.session_pre_log`.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_create_session_series"
down_revision: str | None = "0003_add_reflection_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS hamsatech.session_series (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES hamsatech.sessions(session_id),
    series_number INTEGER NOT NULL,
    total_score NUMERIC,
    shots_fired INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    CONSTRAINT session_series_session_id_series_number_key UNIQUE (session_id, series_number)
);
"""

_DROP_TABLE = "DROP TABLE IF EXISTS hamsatech.session_series;"


def upgrade() -> None:
    op.execute(_CREATE_TABLE)


def downgrade() -> None:
    """Drops the table entirely — a genuine revert, not a no-op: all series data is discarded."""
    op.execute(_DROP_TABLE)
