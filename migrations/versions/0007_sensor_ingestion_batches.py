"""create hamsatech.sensor_ingestion_batches (ECG/ACC batch idempotency)

Revision ID: 0007_sensor_ingestion_batches
Revises: 0006_add_sensor_stream_indexes
Create Date: 2026-10-05

A client uploading ECG/ACC batches retries after a timeout. If the first
request was actually committed and only its response was lost, the retry
would insert the same samples a second time. This table is the ledger that
prevents that: every accepted batch records its client-generated
`batch_id`, and the primary key `(session_id, stream_type, batch_id)` makes
a second insert of the same batch impossible at the database level (the
application claims a batch with `INSERT ... ON CONFLICT DO NOTHING` in the
same transaction as the sample rows — see
`app.modules.sensor_streams.repositories.sensor_stream_repository`).

Like `0004_create_session_series` / `0005_create_daily_checkins`, this
creates a brand-new table in the `hamsatech` schema, hand-written as raw
SQL with `IF NOT EXISTS`, mapped with `ExternalBase`
(`app/models/sensor_ingestion_batch.py`) and excluded from
`target_metadata`. It creates nothing else and touches no existing table,
column, index or row.

Design notes:
- No `batch_id` column is added to `ecg_stream` / `acc_stream`: one small
  row per batch here is far cheaper than 16 bytes on every sample row.
- No foreign key to `hamsatech.sessions`: consistent with the stream tables
  themselves (which have none), and it keeps this ledger from ever blocking
  an operation on a session row. Ownership is enforced by the application
  before a batch is claimed.
- `stream_type` is constrained to the two streams that exist.
- The primary-key index is the only index: every lookup is by the full key.

Rows only matter while a client might still retry a batch (minutes), so
old rows can be purged at any time without affecting stored samples.

`downgrade()` drops only this table — sample data in `ecg_stream` /
`acc_stream` is not affected.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_sensor_ingestion_batches"
down_revision: str | None = "0006_add_sensor_stream_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS hamsatech.sensor_ingestion_batches (
    session_id UUID NOT NULL,
    stream_type TEXT NOT NULL,
    batch_id UUID NOT NULL,
    athlete_id TEXT NOT NULL,
    accepted_count INTEGER NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT sensor_ingestion_batches_pkey PRIMARY KEY (session_id, stream_type, batch_id),
    CONSTRAINT sensor_ingestion_batches_stream_type_check CHECK (stream_type IN ('ECG', 'ACC')),
    CONSTRAINT sensor_ingestion_batches_accepted_count_check CHECK (accepted_count >= 0)
);
"""

DROP_TABLE = "DROP TABLE IF EXISTS hamsatech.sensor_ingestion_batches;"


def upgrade() -> None:
    op.execute(CREATE_TABLE)


def downgrade() -> None:
    """Drops only the idempotency ledger. Stored ECG/ACC samples are unaffected."""
    op.execute(DROP_TABLE)
