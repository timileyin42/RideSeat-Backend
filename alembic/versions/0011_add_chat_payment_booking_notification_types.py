"""Add CHAT, PAYMENT, BOOKING to notificationtype enum.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-30
"""

from __future__ import annotations

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'CHAT'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'PAYMENT'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'BOOKING'")


def downgrade() -> None:
    pass
