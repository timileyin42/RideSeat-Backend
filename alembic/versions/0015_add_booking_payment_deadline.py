"""Add payment_deadline to bookings

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-04
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS "
        "payment_deadline TIMESTAMP WITH TIME ZONE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS payment_deadline")
