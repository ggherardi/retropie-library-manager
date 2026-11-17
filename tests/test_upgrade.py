import json

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Table, select

from backend.config import PROJECT
from backend.db import make_engine, now
from backend.main import create_app


def test_upgrade_preserves_increment1_library(tmp_path):
    data = tmp_path / "existing-library"
    engine = make_engine(data)
    config = Config(str(PROJECT / "alembic.ini"))
    config.attributes["engine"] = engine
    command.upgrade(config, "0001")
    metadata = MetaData()
    games = Table("games", metadata, autoload_with=engine)
    settings = Table("settings", metadata, autoload_with=engine)
    original = dict(
        id=42,
        title="Personal title",
        platform="gb",
        region="Europe",
        year=1998,
        genre="Puzzle",
        description="Manual notes",
        cover_path="",
        size=123,
        format="gb",
        local_path=str(tmp_path / "external.gb"),
        sha256="a" * 64,
        favorite=True,
        provenance="Original source",
        license="Personal record",
        files=[],
        created_at=now(),
    )
    with engine.begin() as db:
        db.execute(games.insert(), original)
        db.execute(settings.insert(), {"key": "custom", "value": {"preserved": True}})
    with TestClient(create_app(data)) as client:
        response = client.get("/api/games/42")
        assert response.status_code == 200
        migrated = response.json()
        for key, value in original.items():
            if key != "created_at":
                assert migrated[key] == value
        assert migrated["author"] == ""
        assert client.get("/api/stats").json()["games"] == 1
    with engine.connect() as db:
        assert db.execute(select(settings.c.value)).scalar_one() == {"preserved": True}
        assert json.loads(db.exec_driver_sql("SELECT files FROM games WHERE id=42").scalar_one()) == []
    engine.dispose()
