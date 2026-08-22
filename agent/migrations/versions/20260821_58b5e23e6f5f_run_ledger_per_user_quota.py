"""run ledger: per-user quota

Gives `runs` an owner, so it can be the quota ledger as well as the analytics table.

Two deliberate departures from what autogenerate produced:

  - Constraints are named. SQLite has no ALTER for constraints, so Alembic rebuilds the
    table in batch mode — and it cannot drop a constraint it has no name for, which would
    have left `downgrade()` broken.
  - Only `runs` is touched. Autogenerate also reported missing indexes on `sessions` and
    a NOT NULL on `users.email_verified`, but that drift is an artefact of *this*
    developer's database, which predates Alembic and was stamped rather than built. A
    database built by the migration chain already has them, so adding them here would
    fail on a fresh install. That gap belongs in its own migration, not smuggled into a
    feature change.

Revision ID: 58b5e23e6f5f
Revises: 79cb9172ead1
Created: 2026-08-21 18:57:27.574306
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "58b5e23e6f5f"
down_revision = "79cb9172ead1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        # Nullable: rows written before quotas existed have no owner, and inventing one
        # would be inventing history. They simply don't count against anyone.
        batch_op.add_column(sa.Column("user_id", sa.String(length=36), nullable=True))
        # A run outlives the diagram it drew — deleting the diagram must not refund it.
        batch_op.alter_column("session_id", existing_type=sa.VARCHAR(length=36), nullable=True)
        batch_op.create_index(batch_op.f("ix_runs_user_id"), ["user_id"], unique=False)
        # The global daily cap counts rows since midnight on every generation request.
        batch_op.create_index(batch_op.f("ix_runs_created_at"), ["created_at"], unique=False)
        batch_op.create_foreign_key("fk_runs_user_id_users", "users", ["user_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_constraint("fk_runs_user_id_users", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_runs_created_at"))
        batch_op.drop_index(batch_op.f("ix_runs_user_id"))
        batch_op.alter_column("session_id", existing_type=sa.VARCHAR(length=36), nullable=False)
        batch_op.drop_column("user_id")
