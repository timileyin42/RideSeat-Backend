"""Add REFUNDED to paymentstatus and GENERAL to notificationtype enums.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-30
"""

from __future__ import annotations

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'REFUNDED'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'GENERAL'")


def downgrade() -> None:
    pass
