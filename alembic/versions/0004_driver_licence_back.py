"""Add driver_license_back_url column to users.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-19
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS driver_license_back_url VARCHAR(500)")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS driver_license_back_url")
