"""Add is_disputed and dispute_reason to bookings.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("is_disputed", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("bookings", sa.Column("dispute_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "dispute_reason")
    op.drop_column("bookings", "is_disputed")
