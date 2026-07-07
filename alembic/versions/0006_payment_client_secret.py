"""add stripe_client_secret to payments

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-07
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS stripe_client_secret VARCHAR(500)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE payments DROP COLUMN IF EXISTS stripe_client_secret"
    )
