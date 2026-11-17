import json
import shutil
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from backend.db import Game
from backend.paths import digest, local_path


class ExportTransport(Protocol):
    """A future SFTP transport consumes the same verified manifest."""

    def publish(self, games: list[Game], destination: Path, dry_run: bool) -> dict: ...


class LocalTransport:
    def publish(self, games: list[Game], destination: Path, dry_run: bool) -> dict:
        manifest: dict[str, Any] = {"version": 1, "target": "RetroPie", "games": [], "total_bytes": 0}
        copies = []
        generated = []
        for game in games:
            folder = f"{game.platform}/game-{game.id}"
            records = []
            for file in game.files:
                source = local_path(file["path"])
                if source.stat().st_size != file["size"] or digest(source) != file["sha256"]:
                    raise ValueError(f"File modificato dopo l'importazione: {source.name}")
                relative = Path(file["relative"])
                if relative.is_absolute() or ".." in relative.parts or ":" in str(relative):
                    raise ValueError("Percorso del manifest non valido")
                target = f"{folder}/{relative.as_posix()}"
                records.append({"path": target, "size": file["size"], "sha256": file["sha256"]})
                copies.append((source, target, file["sha256"]))
            launch = f"{folder}/{game.files[0]['relative']}"
            if game.format == "multidisc":
                entries = [
                    f["relative"]
                    for f in game.files
                    if Path(f["relative"]).suffix.lower() in {".cue", ".chd", ".iso", ".pbp"}
                ]
                playlist = "\n".join(entries) + "\n"
                launch = f"{folder}/discs.m3u"
                generated.append((launch, playlist))
            manifest["games"].append(
                {
                    "id": game.id,
                    "title": game.title,
                    "platform": game.platform,
                    "launch": launch,
                    "files": records,
                    "license": game.license,
                    "provenance": game.provenance,
                    "author": game.author,
                }
            )
        manifest["total_bytes"] = sum(f["size"] for g in manifest["games"] for f in g["files"]) + sum(
            len(s.encode()) for _, s in generated
        )
        manifest["generated_playlists"] = [{"path": p, "content": s} for p, s in generated]
        encoded = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        required = manifest["total_bytes"] + len(encoded)
        free = shutil.disk_usage(destination).free
        if required > free:
            raise ValueError("Spazio disponibile insufficiente")
        result = {"manifest": manifest, "required_bytes": required, "free_bytes": free, "dry_run": dry_run}
        if dry_run:
            return result
        export_id = str(uuid4())
        staging = destination / f".partial-{export_id}"
        final = destination / f"retropie-{export_id}"
        staging.mkdir()
        try:
            for source, name, sha in copies:
                output_path = staging / name
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, output_path)
                if digest(output_path) != sha:
                    raise ValueError("Verifica della copia fallita")
            for name, content in generated:
                (staging / name).write_bytes(content.encode("utf-8"))
            (staging / "manifest.json").write_bytes(encoded)
            staging.rename(final)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return {**result, "destination": str(final)}
