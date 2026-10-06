"""add (session_id, recorded_at) indexes to hamsatech.ecg_stream / acc_stream

Revision ID: 0006_add_sensor_stream_indexes
Revises: 0005_create_daily_checkins
Create Date: 2026-10-05

`hamsatech.ecg_stream` and `hamsatech.acc_stream` are existing,
externally-owned tables that predate this project's migration history
(mapped with `ExternalBase` in `app/models/ecg_stream.py` /
`app/models/acc_stream.py`, excluded from `target_metadata`). A read-only
inspection of the live database showed each has only its primary-key index
on `id`.

Every read of these streams is "one session's samples, in time order", and
both tables grow at sensor rate (ECG ~468,000 rows per streamed hour), so
without an index on `(session_id, recorded_at)` each such read is a full
table scan. This migration adds exactly that index to each table — nothing
else: no table, column, constraint, or row is created, altered, or removed.

Hand-written raw SQL with `IF NOT EXISTS`, matching every other
`hamsatech.*` migration in this project, so it is safe to run whether or
not the index was already created manually.

Operational note: a plain `CREATE INDEX` holds a lock that blocks writes to
the table while the index builds. Both tables are effectively empty today
(0 and ~123 rows), so the build is instantaneous. If this migration is
first applied after ingestion has accumulated significant data, build the
indexes outside Alembic with `CREATE INDEX CONCURRENTLY IF NOT EXISTS ...`
(same names/columns as below; `CONCURRENTLY` cannot run inside Alembic's
transaction), then `alembic stamp 0006_add_sensor_stream_indexes`.

`downgrade()` drops only these two indexes.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_add_sensor_stream_indexes"
down_revision: str | None = "0005_create_daily_checkins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CREATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_ecg_stream_session_id_recorded_at "
    "ON hamsatech.ecg_stream (session_id, recorded_at);",
    "CREATE INDEX IF NOT EXISTS ix_acc_stream_session_id_recorded_at "
    "ON hamsatech.acc_stream (session_id, recorded_at);",
)

_DROP_INDEXES = (
    "DROP INDEX IF EXISTS hamsatech.ix_ecg_stream_session_id_recorded_at;",
    "DROP INDEX IF EXISTS hamsatech.ix_acc_stream_session_id_recorded_at;",
)


def upgrade() -> None:
    for statement in _CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop only the two indexes created above. No table, column, or row is affected."""
    for statement in _DROP_INDEXES:
        op.execute(statement)
