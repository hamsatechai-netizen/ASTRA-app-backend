"""add reflection columns to hamsatech.session_post_log

Revision ID: 0003_add_reflection_columns
Revises: 0002_add_onboarding_columns
Create Date: 2026-08-16

`hamsatech.session_post_log` is an existing, externally-owned production
table (see `app/database/external_base.py` / `app/models/session_post_log.py`)
that this project does not create or otherwise migrate — it is
deliberately excluded from `target_metadata` so Alembic autogenerate can
never propose changes to it. This migration is hand-written, following
the same deliberate, reviewed-exception pattern as
`0002_add_onboarding_columns` (which did the same thing for
`hamsatech.athletes`): it adds exactly the 3 columns identified by the
reflection-persistence schema audit as missing from that table, and
touches nothing else — `focus_level`, `focus_area`, `session_duration`,
`performance_rating`, `challenges`, and `coach_feedback` are untouched,
since they carry different, already-in-use semantics.

Every `ADD COLUMN` uses `IF NOT EXISTS`, so this migration is safe to run
more than once. All 3 columns are nullable with no default — a metadata-only
change on PostgreSQL 11+ (no table rewrite, no scan of existing rows).
Existing rows and all other columns/constraints/indexes are untouched.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_add_reflection_columns"
down_revision: str | None = "0002_add_onboarding_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "hamsatech.session_post_log"

_ADD_COLUMN_STATEMENTS = (
    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS mood INTEGER;",
    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS what_worked TEXT;",
    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS what_didnt TEXT;",
)

# Reverse order of the additions above, for a clean, readable revert.
_DROP_COLUMN_STATEMENTS = (
    "ALTER TABLE {table} DROP COLUMN IF EXISTS what_didnt;",
    "ALTER TABLE {table} DROP COLUMN IF EXISTS what_worked;",
    "ALTER TABLE {table} DROP COLUMN IF EXISTS mood;",
)


def upgrade() -> None:
    for statement in _ADD_COLUMN_STATEMENTS:
        op.execute(statement.format(table=_TABLE))


def downgrade() -> None:
    """
    Drops exactly the 3 columns this migration added, nothing else.

    This is a genuine revert, not a no-op: any reflection data entered
    since these columns were added is discarded along with the columns.
    No other column, row, or table on `hamsatech.session_post_log` is
    affected.
    """
    for statement in _DROP_COLUMN_STATEMENTS:
        op.execute(statement.format(table=_TABLE))
