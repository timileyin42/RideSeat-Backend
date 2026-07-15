"""Add trip_status, started_at, completed_at to trips table."""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trips", sa.Column("trip_status", sa.String(20), nullable=False, server_default="ACTIVE"))
    op.add_column("trips", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trips", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("trips", "completed_at")
    op.drop_column("trips", "started_at")
    op.drop_column("trips", "trip_status")
