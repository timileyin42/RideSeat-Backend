"""Add priority enum to tickets table.

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

ticketpriority_enum = sa.Enum("LOW", "MEDIUM", "HIGH", name="ticketpriority")


def upgrade() -> None:
    ticketpriority_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "tickets",
        sa.Column(
            "priority",
            ticketpriority_enum,
            nullable=False,
            server_default="MEDIUM",
        ),
    )


def downgrade() -> None:
    op.drop_column("tickets", "priority")
    ticketpriority_enum.drop(op.get_bind(), checkfirst=True)
