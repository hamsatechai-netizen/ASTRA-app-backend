"""add onboarding columns to hamsatech.athletes

Revision ID: 0002_add_onboarding_columns
Revises: 0001_create_otp_challenges
Create Date: 2026-07-18

`hamsatech.athletes` is an existing, externally-owned production table
(see `app/database/external_base.py` / `app/models/hamsatech_athlete.py`)
that this project does not create or otherwise migrate — it is
deliberately excluded from `target_metadata` so Alembic autogenerate can
never propose changes to it. This migration is hand-written and is the
one deliberate, reviewed exception: it adds exactly the 8 columns
identified by the onboarding-screen schema analysis as missing from
that table, and touches nothing else.

Every `ADD COLUMN` uses `IF NOT EXISTS`, so this migration is safe to
run more than once (e.g. if a column were ever added out-of-band). All
8 columns are nullable; `current_onboarding_step` additionally carries
a constant `DEFAULT 1`. A nullable column add with no default, or with
a constant default, is a metadata-only change on PostgreSQL 11+ (no
table rewrite, no scan of existing rows) — existing rows are not
touched and no other column, constraint, index, or table is referenced.

Revision id kept to 27 characters deliberately: Alembic's default
`alembic_version.version_num` column is `VARCHAR(32)`, and the original
`0002_add_athlete_onboarding_columns` (35 chars) overflowed it —
discovered when `alembic upgrade head` rolled back cleanly (transactional
DDL) on a `StringDataRightTruncationError` from the version-bookkeeping
UPDATE, after the ADD COLUMN statements themselves had already succeeded
in the same transaction.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_onboarding_columns"
down_revision: str | None = "0001_create_otp_challenges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "hamsatech.athletes"

_ADD_COLUMN_STATEMENTS = (
    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS city TEXT;",
    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS years_shooting INTEGER;",
    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS avg_practice_score NUMERIC;",
    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS target_score NUMERIC;",
    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS performance_blockers TEXT[];",
    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS goal_30_day TEXT;",
    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS goal_6_month TEXT;",
    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS current_onboarding_step SMALLINT DEFAULT 1;",
)

# Reverse order of the additions above, for a clean, readable revert.
_DROP_COLUMN_STATEMENTS = (
    "ALTER TABLE {table} DROP COLUMN IF EXISTS current_onboarding_step;",
    "ALTER TABLE {table} DROP COLUMN IF EXISTS goal_6_month;",
    "ALTER TABLE {table} DROP COLUMN IF EXISTS goal_30_day;",
    "ALTER TABLE {table} DROP COLUMN IF EXISTS performance_blockers;",
    "ALTER TABLE {table} DROP COLUMN IF EXISTS target_score;",
    "ALTER TABLE {table} DROP COLUMN IF EXISTS avg_practice_score;",
    "ALTER TABLE {table} DROP COLUMN IF EXISTS years_shooting;",
    "ALTER TABLE {table} DROP COLUMN IF EXISTS city;",
)


def upgrade() -> None:
    for statement in _ADD_COLUMN_STATEMENTS:
        op.execute(statement.format(table=_TABLE))


def downgrade() -> None:
    """
    Drops exactly the 8 columns this migration added, nothing else.

    This is a genuine revert, not a no-op: any data entered into these
    columns since they were added is discarded along with the columns.
    No other column, row, or table on `hamsatech.athletes` is affected.
    """
    for statement in _DROP_COLUMN_STATEMENTS:
        op.execute(statement.format(table=_TABLE))
