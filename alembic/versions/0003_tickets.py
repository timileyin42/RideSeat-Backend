"""Add tickets table with category and status enums.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-17
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TICKET_CATEGORY = ("HARASSMENT", "FRAUD", "SAFETY", "MISCONDUCT", "NO_SHOW", "PROPERTY_DAMAGE", "OTHER")
TICKET_STATUS = ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED")


def upgrade() -> None:
    # DO blocks are idempotent — swallow duplicate_object from prior failed runs
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE ticketcategory AS ENUM (
                'HARASSMENT','FRAUD','SAFETY','MISCONDUCT','NO_SHOW','PROPERTY_DAMAGE','OTHER'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE ticketstatus AS ENUM ('OPEN','IN_PROGRESS','RESOLVED','CLOSED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Raw SQL for table creation — bypasses SQLAlchemy's auto-DDL which re-emits CREATE TYPE
    op.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id              UUID PRIMARY KEY,
            reporter_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reported_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            trip_id         UUID REFERENCES trips(id) ON DELETE SET NULL,
            category        ticketcategory NOT NULL,
            subject         VARCHAR(200) NOT NULL,
            description     TEXT NOT NULL,
            status          ticketstatus NOT NULL DEFAULT 'OPEN',
            admin_note      TEXT,
            resolved_by     UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at      TIMESTAMPTZ NOT NULL,
            updated_at      TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tickets_reporter_id ON tickets (reporter_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tickets_status ON tickets (status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tickets")
    op.execute("DROP TYPE IF EXISTS ticketcategory")
    op.execute("DROP TYPE IF EXISTS ticketstatus")
