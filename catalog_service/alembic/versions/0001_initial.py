"""create servers and processed_events, seed catalog

Revision ID: 0001
Revises:
"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

STATUS = postgresql.ENUM("active", "removed", name="server_status", create_type=False)
PROVIDER = "00000000-0000-4000-8000-0000000000aa"


def upgrade() -> None:
    STATUS.create(op.get_bind(), checkfirst=True)
    servers = op.create_table(
        "servers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("game", sa.String, nullable=False),
        sa.Column("region", sa.String, nullable=False),
        sa.Column("slots", sa.Integer, nullable=False),
        sa.Column("price_per_hour", sa.Numeric(10, 2), nullable=False),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("rating_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", STATUS, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_servers_game", "servers", ["game"])
    op.create_index("ix_servers_region", "servers", ["region"])
    op.create_table("processed_events", sa.Column("event_id", sa.String, primary_key=True))
    now = datetime.now(timezone.utc)
    seed = [
        ("11111111-1111-4111-8111-111111111111", "Minecraft 8 GB", "minecraft", "eu", 20, 150),
        ("22222222-2222-4222-8222-222222222222", "CS2 Competitive", "cs2", "eu", 10, 250),
        ("33333333-3333-4333-8333-333333333333", "ARK Survival", "ark", "us", 30, 400),
        ("44444444-4444-4444-8444-444444444444", "Minecraft Lite", "minecraft", "us", 8, 90),
    ]
    op.bulk_insert(servers, [dict(id=i, name=n, game=g, region=r, slots=s, price_per_hour=p, provider_id=PROVIDER,
                                  status="active", created_at=now, rating_count=0) for i, n, g, r, s, p in seed])


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_table("servers")
    STATUS.drop(op.get_bind(), checkfirst=True)
