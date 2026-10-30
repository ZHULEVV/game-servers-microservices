"""create payments and processed_events

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

STATUS = postgresql.ENUM("pending", "succeeded", "failed", "refunded", name="payment_status", create_type=False)


def upgrade() -> None:
    STATUS.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", STATUS, nullable=False),
        sa.Column("card_token", sa.String, nullable=True),
        sa.Column("fail_reason", sa.String, nullable=True),
        sa.Column("refund_reason", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"])
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_table("processed_events", sa.Column("event_id", sa.String, primary_key=True))


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_table("payments")
    STATUS.drop(op.get_bind(), checkfirst=True)
