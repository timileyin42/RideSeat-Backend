"""Add REJECTED to bookingstatus enum.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add REJECTED to the bookingstatus enum
    op.execute("ALTER TYPE bookingstatus ADD VALUE IF NOT EXISTS 'REJECTED'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't allow removing enum values easily
    # We'll just leave it as is since removing values can cause data issues
    pass
