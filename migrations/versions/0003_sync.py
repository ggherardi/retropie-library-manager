"""Devices, persistent sync plans/reports and publisher metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade():
    op.add_column("games", sa.Column("publisher", sa.String(500), nullable=False, server_default=""))
    op.create_table(
        "devices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(100), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("diagnostics", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
    )
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("device_id", "status"):
        op.create_index(f"ix_sync_runs_{column}", "sync_runs", [column])


def downgrade():
    op.drop_table("sync_runs")
    op.drop_table("devices")
    with op.batch_alter_table("games") as batch:
        batch.drop_column("publisher")
