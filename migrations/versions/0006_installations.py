"""Persistent installation orchestration; no changes to existing library tables."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade():
    op.create_table(
        "installation_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_key", sa.String(100), nullable=False, unique=True),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("control", sa.String(20), nullable=False),
        sa.Column("authorized", sa.Boolean(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("error", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_installation_batches_status", "installation_batches", ["status"])
    op.create_table(
        "installation_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("phase", sa.String(40), nullable=False),
        sa.Column("candidate", sa.JSON(), nullable=False),
        sa.Column("identification", sa.JSON(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("sync_run_id", sa.String(36), nullable=False),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("error", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("enriched", sa.Boolean(), nullable=False),
        sa.Column("visibility", sa.String(30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_retry", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", "source_key"),
    )
    for field in ["batch_id", "status", "game_id"]:
        op.create_index("ix_installation_items_" + field, "installation_items", [field])
    op.create_table(
        "installation_uploads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("relative", sa.Text(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("received", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("chunks", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint("batch_id", "relative"),
    )
    op.create_index("ix_installation_uploads_batch_id", "installation_uploads", ["batch_id"])


def downgrade():
    for table in ["installation_uploads", "installation_items", "installation_batches"]:
        op.drop_table(table)
