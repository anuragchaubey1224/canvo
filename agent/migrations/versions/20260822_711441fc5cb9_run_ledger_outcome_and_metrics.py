"""run ledger: outcome and metrics

Closes the loop on the run row. It is created before the graph starts, because the quota
has to be spent before anything is generated; these two columns are what the run leaves
behind when it finishes, so the ledger doubles as the telemetry table rather than needing
a second one (EVAL-PLAN.md §3).

`outcome` is indexed because almost every question starts by filtering on it — how many
failed, how many were stopped, how many refused. `metrics` is one `app.eval.RunRecord` as
JSON; a column per field would need a migration every time a metric is added, and these
rows are read in bulk rather than filtered on.

Scoped to `runs` on purpose. Autogenerate also reported missing indexes on `sessions` and
a NOT NULL on `users.email_verified`, but that drift only exists in a database that
predates Alembic and was stamped rather than built — a fresh install already has them, so
including them here would fail on one of the two. Same reasoning as 58b5e23e6f5f.

Revision ID: 711441fc5cb9
Revises: 58b5e23e6f5f
Created: 2026-08-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "711441fc5cb9"
down_revision = "58b5e23e6f5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        # Null until the run finishes — which is also how an abandoned run is spotted.
        batch_op.add_column(sa.Column("outcome", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("metrics", sa.Text(), nullable=True))
        batch_op.create_index(batch_op.f("ix_runs_outcome"), ["outcome"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_runs_outcome"))
        batch_op.drop_column("metrics")
        batch_op.drop_column("outcome")
