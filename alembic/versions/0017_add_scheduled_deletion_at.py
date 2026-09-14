"""Add scheduled_deletion_at to users for 30-day soft delete flow.

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-14
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS scheduled_deletion_at TIMESTAMP WITH TIME ZONE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS scheduled_deletion_at")
