"""add apple_refresh_token to users

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS apple_refresh_token TEXT DEFAULT NULL;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS apple_refresh_token;")
