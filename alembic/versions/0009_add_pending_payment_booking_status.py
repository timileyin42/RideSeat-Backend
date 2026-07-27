"""Add PENDING_PAYMENT to bookingstatus enum.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-27
"""

from __future__ import annotations

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE bookingstatus ADD VALUE IF NOT EXISTS 'PENDING_PAYMENT'")


def downgrade() -> None:
    pass
