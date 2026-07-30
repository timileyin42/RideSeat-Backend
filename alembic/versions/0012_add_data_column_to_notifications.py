"""Add data JSON column to notifications table.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("data", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("notifications", "data")
