"""Make first_name and last_name nullable (signup now email+password only).

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-17
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "first_name", nullable=True)
    op.alter_column("users", "last_name", nullable=True)


def downgrade() -> None:
    # Backfill before reverting — set empty string so NOT NULL is satisfied
    op.execute("UPDATE users SET first_name = '' WHERE first_name IS NULL")
    op.execute("UPDATE users SET last_name = '' WHERE last_name IS NULL")
    op.alter_column("users", "first_name", nullable=False)
    op.alter_column("users", "last_name", nullable=False)
