"""add apple_user_id to users

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS apple_user_id VARCHAR(255) DEFAULT NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_users_apple_user_id
        ON users (apple_user_id)
        WHERE apple_user_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_apple_user_id;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS apple_user_id;")
