"""Add tickets table with category and status enums.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TICKET_CATEGORY = ("HARASSMENT", "FRAUD", "SAFETY", "MISCONDUCT", "NO_SHOW", "PROPERTY_DAMAGE", "OTHER")
TICKET_STATUS = ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED")


def upgrade() -> None:
    # IF NOT EXISTS makes this idempotent — safe even if a prior failed run created the types
    op.execute("CREATE TYPE IF NOT EXISTS ticketcategory AS ENUM ('HARASSMENT', 'FRAUD', 'SAFETY', 'MISCONDUCT', 'NO_SHOW', 'PROPERTY_DAMAGE', 'OTHER')")
    op.execute("CREATE TYPE IF NOT EXISTS ticketstatus AS ENUM ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')")

    op.create_table(
        "tickets",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("reporter_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reported_user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trip_id", sa.UUID(), sa.ForeignKey("trips.id", ondelete="SET NULL"), nullable=True),
        # create_type=False — types already created above; prevents SQLAlchemy auto-DDL double-creation
        sa.Column("category", sa.Enum(*TICKET_CATEGORY, name="ticketcategory", create_type=False), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum(*TICKET_STATUS, name="ticketstatus", create_type=False), nullable=False, server_default="OPEN"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tickets_reporter_id", "tickets", ["reporter_id"])
    op.create_index("ix_tickets_status", "tickets", ["status"])


def downgrade() -> None:
    op.drop_table("tickets")
    op.execute("DROP TYPE IF EXISTS ticketcategory")
    op.execute("DROP TYPE IF EXISTS ticketstatus")
