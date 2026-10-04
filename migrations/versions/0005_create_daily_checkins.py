"""create hamsatech.daily_checkins

Revision ID: 0005_create_daily_checkins
Revises: 0004_create_session_series
Create Date: 2026-09-07

Like `0004_create_session_series`, this creates a brand new table in the
`hamsatech` schema — the same explicitly-approved exception to "this
project doesn't own the `hamsatech` schema", made because no existing
table represents a recurring daily subjective-state record (confirmed by
a full read-only audit of every table/column in `hamsatech` before this
migration was written — see the Daily Check-in audit/specification pass).
`hamsatech.session_post_log` (post-session reflection, including its own
`mood` column) is a different, per-session concept and is untouched.

Hand-written and executed via raw SQL (not Alembic's `op.create_table`),
matching every other `hamsatech.*` migration in this project: the table
is mapped with `ExternalBase` (`app/models/daily_checkin.py`), excluded
from `target_metadata`, so autogenerate can never propose further changes
to it — any future change must be another reviewed, hand-written
migration.

`athlete_id` carries a real foreign key to `hamsatech.athletes(athlete_id)`
— safe here because both tables live in the same `hamsatech` schema
(the same intra-schema pattern already used by
`session_series.session_id -> hamsatech.sessions.session_id`), not a
cross-schema reference.

`UNIQUE (athlete_id, checkin_date)` is the natural key a check-in is
identified by — one row per athlete per UTC calendar day (see
`app.modules.checkin.services.checkin_service` for the UTC-date
computation) — enforced with a UNIQUE constraint and used as the ON
CONFLICT target for same-day upserts. `id` is a separate synthetic
primary key, matching the same shape already used by
`hamsatech.session_series`.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_create_daily_checkins"
down_revision: str | None = "0004_create_session_series"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS hamsatech.daily_checkins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    athlete_id TEXT NOT NULL REFERENCES hamsatech.athletes(athlete_id),
    checkin_date DATE NOT NULL,
    mood SMALLINT NOT NULL,
    energy_level SMALLINT NOT NULL,
    sleep_band TEXT NOT NULL,
    tags TEXT[],
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    CONSTRAINT daily_checkins_athlete_id_checkin_date_key UNIQUE (athlete_id, checkin_date)
);
"""

_DROP_TABLE = "DROP TABLE IF EXISTS hamsatech.daily_checkins;"


def upgrade() -> None:
    op.execute(_CREATE_TABLE)


def downgrade() -> None:
    """Drops the table entirely — a genuine revert, not a no-op: all check-in history is discarded."""
    op.execute(_DROP_TABLE)
