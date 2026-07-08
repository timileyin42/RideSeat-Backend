"""unique constraint on payments.booking_id

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-07
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_payments_booking_id'
            ) THEN
                ALTER TABLE payments ADD CONSTRAINT uq_payments_booking_id UNIQUE (booking_id);
            END IF;
        END$$;
    """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE payments DROP CONSTRAINT IF EXISTS uq_payments_booking_id"
    )
