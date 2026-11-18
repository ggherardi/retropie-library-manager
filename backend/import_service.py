"""Shared, idempotent import of a reviewed candidate. Originals are never changed."""

from pathlib import Path

from sqlalchemy import select

from backend.db import Game
from backend.paths import allowed, digest


def logical_files(files):
    # A playlist adds an entry point, not a second copy of the same complete disc set.
    return sorted((f["sha256"], f["size"]) for f in files if Path(f["path"]).suffix.lower() != ".m3u")


def import_candidate(
    db,
    item,
    roots,
    provenance="Importazione locale",
    license="Da verificare",
    checkpoint=lambda: None,
    on_verified=lambda: None,
):
    for file in item["files"]:
        path = allowed(file["path"], roots)
        if path.stat().st_size != file["size"] or digest(path, checkpoint) != file["sha256"]:
            raise ValueError(f"File cambiato dall'anteprima: {path.name}. Ripetere l'analisi.")
    on_verified()
    existing = db.scalar(select(Game).where(Game.sha256 == item["sha256"]))
    if not existing and item.get("existing_game_id"):
        proposed = db.get(Game, item["existing_game_id"])
        if (
            proposed
            and proposed.platform == item["platform"]
            and logical_files(proposed.files) == logical_files(item["files"])
        ):
            existing = proposed
    if existing:
        # An identical, explicitly selected copy can restore a missing source path.
        if not all(Path(f["path"]).is_file() for f in existing.files):
            if item["sha256"] != existing.sha256:
                raise ValueError(
                    "Dischi già catalogati ma sorgente originale mancante: selezionare i CUE originali per ripristinare i percorsi"
                )
            existing.files, existing.local_path = item["files"], item["local_path"]
        return existing, True
    fields = {column.name for column in Game.__table__.columns} - {
        "id",
        "created_at",
        "provenance",
        "license",
    }
    values = {k: v for k, v in item.items() if k in fields}
    game = Game(**values, provenance=provenance, license=license)
    db.add(game)
    db.flush()
    return game, False
