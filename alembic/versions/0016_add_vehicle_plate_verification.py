"""Add vehicle plate verification columns to users table.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-21
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS vehicle_plate_verified BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS vehicle_plate_verified_at TIMESTAMP WITH TIME ZONE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS vehicle_plate_verified_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS vehicle_plate_verified")
