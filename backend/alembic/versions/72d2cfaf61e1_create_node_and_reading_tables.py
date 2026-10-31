"""create node and reading tables

Revision ID: 72d2cfaf61e1
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "72d2cfaf61e1"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "node",
        sa.Column("node_id", sa.String(64), primary_key=True),
        sa.Column("node_type", sa.String(16), nullable=False),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_battery_v", sa.Numeric(5, 2), nullable=True),
        sa.Column("last_rssi_dbm", sa.Integer, nullable=True),
    )

    op.create_table(
        "reading",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "node_id",
            sa.String(64),
            sa.ForeignKey("node.node_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Numeric(10, 4), nullable=False),
        sa.UniqueConstraint("node_id", "metric", "ts", name="uq_node_metric_ts"),
        sa.Index("ix_node_metric_ts", "node_id", "metric", "ts"),
    )


def downgrade() -> None:
    op.drop_table("reading")
    op.drop_table("node")
