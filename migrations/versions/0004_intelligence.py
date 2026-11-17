"""Versioned metadata catalogs, validation, core evidence and collections."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"

# Independent, frozen metadata: future ORM changes must not alter this migration.
TABLES = {
    "catalog_sources": [
        ("id", "s80", "pk"),
        ("name", "s300", ""),
        ("config", "json", ""),
        ("active_run", "s36", "ix"),
        ("sha256", "s64", ""),
        ("updated_at", "date", ""),
    ],
    "catalog_entries": [
        ("id", "int", "pk"),
        ("run_id", "s36", "ix"),
        ("source_id", "s80", "ix"),
        ("uid", "s64", "ix"),
        ("name", "s300", "ix"),
        ("title", "s500", ""),
        ("platform", "s30", "ix"),
        ("system", "s100", "ix"),
        ("manufacturer", "s300", ""),
        ("year", "s20", ""),
        ("genre", "s120", "ix"),
        ("players", "int", "null"),
        ("orientation", "s30", ""),
        ("controls", "s300", ""),
        ("parent", "s300", "ix"),
        ("family", "s300", "ix"),
        ("romof", "s300", ""),
        ("kind", "s20", "ix"),
        ("components", "json", ""),
        ("details", "json", ""),
        ("payload_sha", "s64", ""),
    ],
    "catalog_runs": [
        ("id", "s36", "pk"),
        ("kind", "s30", ""),
        ("source_id", "s80", ""),
        ("status", "s30", "ix"),
        ("progress", "json", ""),
        ("result", "json", ""),
        ("error", "text", ""),
        ("created_at", "date", ""),
    ],
    "game_insights": [
        ("game_id", "int", "pk"),
        ("catalog_uid", "s64", "ix"),
        ("preferred_core", "s100", ""),
        ("machine_mode", "s20", ""),
        ("asset_kind", "s20", ""),
        ("test_status", "s20", "ix"),
        ("test_evidence", "json", ""),
        ("screenshot_path", "text", ""),
    ],
    "arcade_validations": [
        ("game_id", "int", "pk"),
        ("catalog_uid", "s64", "ix"),
        ("source_sha", "s64", ""),
        ("archive_sha", "s64", ""),
        ("mode", "s20", ""),
        ("status", "s30", "ix"),
        ("report", "json", ""),
        ("checked_at", "date", ""),
    ],
    "catalog_preferences": [("family_key", "s150", "pk"), ("preferred_uid", "s64", "")],
    "core_bindings": [
        ("id", "s64", "pk"),
        ("device_id", "s36", "ix"),
        ("source_id", "s80", ""),
        ("core", "s100", ""),
        ("source_sha", "s64", ""),
        ("binary_sha", "s64", ""),
        ("version", "s300", ""),
        ("evidence", "text", ""),
        ("checked_at", "date", ""),
    ],
    "sync_presence": [
        ("id", "int", "pk"),
        ("game_id", "int", "ix"),
        ("device_id", "s36", "ix"),
        ("sha256", "s64", ""),
        ("run_id", "s36", ""),
        ("checked_at", "date", ""),
    ],
}


def upgrade():
    kinds = {"int": sa.Integer(), "json": sa.JSON(), "text": sa.Text(), "date": sa.DateTime(timezone=True)}
    for table, fields in TABLES.items():
        columns = [
            sa.Column(
                name,
                sa.String(int(kind[1:])) if kind.startswith("s") else kinds[kind],
                primary_key=flag == "pk",
                nullable=flag == "null",
            )
            for name, kind, flag in fields
        ]
        if table == "catalog_entries":
            columns.append(sa.UniqueConstraint("run_id", "name"))
        if table == "sync_presence":
            columns.append(sa.UniqueConstraint("game_id", "device_id"))
        op.create_table(table, *columns)
        for name, _kind, flag in fields:
            if flag == "ix":
                op.create_index("ix_" + table + "_" + name, table, [name])
    op.create_index("ix_catalog_page", "catalog_entries", ["run_id", "platform", "title"])
    op.execute(
        "CREATE VIRTUAL TABLE catalog_fts USING fts5(title, name, manufacturer, content='catalog_entries', content_rowid='id', tokenize='unicode61 remove_diacritics 2')"
    )
    op.execute(
        "CREATE TRIGGER catalog_fts_insert AFTER INSERT ON catalog_entries BEGIN INSERT INTO catalog_fts(rowid,title,name,manufacturer) VALUES(new.id,new.title,new.name,new.manufacturer); END"
    )
    op.execute(
        "CREATE TRIGGER catalog_fts_delete AFTER DELETE ON catalog_entries BEGIN INSERT INTO catalog_fts(catalog_fts,rowid,title,name,manufacturer) VALUES('delete',old.id,old.title,old.name,old.manufacturer); END"
    )


def downgrade():
    op.execute("DROP TRIGGER catalog_fts_insert")
    op.execute("DROP TRIGGER catalog_fts_delete")
    op.execute("DROP TABLE catalog_fts")
    for table in reversed(TABLES):
        op.drop_table(table)
