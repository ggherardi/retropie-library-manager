"""Curated classics, explicit membership and media provenance; preserve library data."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade():
    op.create_table(
        "essential_classics",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("genre", sa.String(120), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    for field in ["title", "platform", "genre"]:
        op.create_index("ix_essential_classics_" + field, "essential_classics", [field])
    op.create_table(
        "game_curation",
        sa.Column("game_id", sa.Integer(), primary_key=True),
        sa.Column("classic_id", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("matched_sha", sa.String(64), nullable=False),
        sa.Column("match_basis", sa.String(100), nullable=False),
        sa.Column("metadata_status", sa.String(20), nullable=False),
        sa.Column("metadata_note", sa.Text(), nullable=False),
        sa.Column("metadata_fingerprint", sa.String(64), nullable=False),
    )
    op.create_index("ix_game_curation_classic_id", "game_curation", ["classic_id"])
    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_media_assets_game_id", "media_assets", ["game_id"])
    op.create_table(
        "media_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
    )


def downgrade():
    for table in ["media_plans", "media_assets", "game_curation", "essential_classics"]:
        op.drop_table(table)
