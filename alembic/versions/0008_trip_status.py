"""Add trip_status, started_at, completed_at to trips table."""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='trips' AND column_name='trip_status') THEN
                ALTER TABLE trips ADD COLUMN trip_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='trips' AND column_name='started_at') THEN
                ALTER TABLE trips ADD COLUMN started_at TIMESTAMPTZ;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='trips' AND column_name='completed_at') THEN
                ALTER TABLE trips ADD COLUMN completed_at TIMESTAMPTZ;
            END IF;
        END$$;
    """)


def downgrade() -> None:
    op.drop_column("trips", "completed_at")
    op.drop_column("trips", "started_at")
    op.drop_column("trips", "trip_status")
