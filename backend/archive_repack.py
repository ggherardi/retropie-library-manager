"""Create deterministic ZIP copies only after a complete DAT match, then revalidate."""

import json
import os
import shutil
import zipfile
from pathlib import Path
from uuid import uuid4

from backend.archive_import import RESERVE, ArchiveStore, Budget, _inventory, safe_name
from backend.archive_volumes import source_parts
from backend.paths import digest


def repack(data, archives):
    store = ArchiveStore(data)
    budget = Budget(lambda: None)
    result = {}
    for name, original in archives.items():
        path = Path(original["path"])
        if digest(path) != original["sha256"]:
            raise ValueError("Set cambiato dopo la validazione DAT")
        if path.suffix.lower() == ".zip" and len(source_parts(path)[1]) == 1:
            result[name] = str(path)
            continue
        entries = _inventory(path)
        prepared, report = store._prepare(path, entries, budget)
        target = prepared.parent / (safe_name(name) + ".zip")
        marker = target.with_suffix(".zip.json")
        if target.exists():
            if not marker.is_file() or digest(target) != json.loads(marker.read_text())["sha256"]:
                raise ValueError("ZIP arcade preparato modificato: nessuna sovrascrittura")
            result[name] = str(target)
            continue
        if report["expanded_bytes"] + 1024**2 + RESERVE > shutil.disk_usage(store.work).free:
            raise ValueError("Spazio PC insufficiente per preparare il formato ZIP arcade")
        work = store.work / ("work-" + str(uuid4()))
        work.mkdir()
        temporary = work / "set.zip"
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
                for member in sorted(report["files"]):
                    budget.check()
                    info = zipfile.ZipInfo(member, (1980, 1, 1, 0, 0, 0))
                    info.external_attr = 0o100644 << 16
                    with (
                        (prepared / member).open("rb") as source,
                        archive.open(info, "w", force_zip64=True) as sink,
                    ):
                        for block in iter(lambda: source.read(65536), b""):
                            budget.check()
                            sink.write(block)
            with temporary.open("rb+") as stream:
                os.fsync(stream.fileno())
            sha = digest(temporary)
            # Publish marker first: an interrupted ZIP rename can be retried safely.
            marker.write_text(
                json.dumps({"sha256": sha, "source": report["archive_sha256"]}), encoding="utf8"
            )
            temporary.rename(target)
            result[name] = str(target)
        finally:
            store.clean(work)
    return result
