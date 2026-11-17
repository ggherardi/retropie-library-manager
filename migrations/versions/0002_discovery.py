"""Discovery metadata and durable, explicitly confirmed acquisition queue."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.add_column("games", sa.Column("author", sa.String(500), nullable=False, server_default=""))
    op.create_table(
        "discovery_entries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("provider_id", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(300), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("author", sa.String(500)),
        sa.Column("year", sa.Integer()),
        sa.Column("genre", sa.String(120)),
        sa.Column("description", sa.Text()),
        sa.Column("license", sa.String(200)),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("size", sa.Integer()),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("downloadable", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("provider_id", "title", "platform", "genre", "license", "sha256"):
        op.create_index(f"ix_discovery_entries_{column}", "discovery_entries", [column])
    op.create_table(
        "provider_states",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "download_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entry_id", sa.String(64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("received", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("retry_at", sa.Float(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("etag", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("game_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("entry_id", "status"):
        op.create_index(f"ix_download_tasks_{column}", "download_tasks", [column])
    op.create_table(
        "download_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("tasks", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    for name in ("download_plans", "download_tasks", "provider_states", "discovery_entries"):
        op.drop_table(name)
    with op.batch_alter_table("games") as batch:
        batch.drop_column("author")
