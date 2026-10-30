"""create bookings and processed_events

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

STATUS = postgresql.ENUM("created", "awaiting_payment", "confirmed", "active", "finished", "cancelled",
                         name="booking_status", create_type=False)


def upgrade() -> None:
    STATUS.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", STATUS, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("cancel_reason", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])
    op.create_index("ix_bookings_server_id", "bookings", ["server_id"])
    op.create_table("processed_events", sa.Column("event_id", sa.String, primary_key=True))


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_table("bookings")
    STATUS.drop(op.get_bind(), checkfirst=True)
