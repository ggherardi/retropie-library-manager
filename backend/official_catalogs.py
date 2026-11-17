"""Explicit metadata-only acquisition from core maintainers; no ROM or BIOS downloads."""

import hashlib
import json
import re
from typing import Literal
from urllib.parse import quote

from backend.intelligence_schemas import CatalogImport
from backend.network import PublicHTTP


def driver_hints(content, path, system):
    """Read explicit BurnDriver identifiers; never infer games from similar titles."""
    hints = {}
    for match in re.finditer(r'struct\s+BurnDriver\w*\s+\w+\s*=\s*\{\s*"([^"\n]+)"([\s\S]*?)\n\};', content):
        name, fields = match.groups()
        info = {"sourcefile": path, "system": system}
        players = re.search(r",\s*(\d+),\s*HARDWARE_[\w |]+,\s*(GBF_[\w |]+),", fields)
        if players:
            info["players"] = players.group(1)
            genres = {
                "GBF_VSFIGHT": "Fighting",
                "GBF_SCRFIGHT": "Beat em up",
                "GBF_VERSHOOT": "Vertical shooter",
                "GBF_HORSHOOT": "Horizontal shooter",
                "GBF_PLATFORM": "Platform",
                "GBF_PUZZLE": "Puzzle",
                "GBF_SPORTSMISC": "Sports",
                "GBF_RACING": "Racing",
                "GBF_MAZE": "Maze",
                "GBF_MISC": "Miscellaneous",
            }
            info["genre"] = genres.get(
                players.group(2), players.group(2).removeprefix("GBF_").replace("_", " ").title()
            )
        hints[name] = info
    return hints


def fetch_catalog(service, body, run_id):
    repo = "libretro/mame2003-libretro" if body.provider == "mame2003" else "libretro/FBNeo"
    core: Literal["lr-mame2003", "lr-fbneo"] = "lr-mame2003" if body.provider == "mame2003" else "lr-fbneo"
    path = (
        "metadata/mame2003.xml"
        if body.provider == "mame2003"
        else "dats/FinalBurn Neo (ClrMame Pro XML, Arcade only).dat"
    )
    revision = "HEAD"
    if body.provider == "fbneo-installed":
        audit = service.audit_device(body.device_id, run_id)
        version = audit["cores"][core].get("version") or ""
        match = re.search(r"\b([a-f0-9]{7,40})\b", version)
        if not match:
            raise ValueError(
                "Revisione Git del core FBNeo non rilevata; importare il DAT corrispondente manualmente"
            )
        revision = match.group(1)
    http = PublicHTTP()
    try:
        commit = json.loads(http.read(f"https://api.github.com/repos/{repo}/commits/{revision}", 2_000_000))[
            "sha"
        ]
        tree = json.loads(
            http.read(f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1", 20_000_000)
        )
        if tree.get("truncated"):
            raise ValueError("Inventario DAT troncato")
        node = next((n for n in tree["tree"] if n["path"] == path and n["type"] == "blob"), None)
        if not node or not 0 < node.get("size", 0) <= 64_000_000:
            raise ValueError("DAT non disponibile nella revisione rilevata")
        folder = service.data_dir / "catalogs"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (node["sha"] + ".xml")
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{quote(path, safe='/')}"
        if not target.exists():
            temporary = folder / (run_id + ".part")
            count = 0
            try:
                with http.stream(url) as response, temporary.open("xb") as output:
                    response.raise_for_status()
                    for block in response.iter_bytes(65536):
                        count += len(block)
                        if count > node["size"]:
                            raise ValueError("Dimensione DAT superiore al manifest Git")
                        service.checkpoint(
                            run_id,
                            {"phase": "Download metadati DAT", "bytes": count, "total_bytes": node["size"]},
                        )
                        output.write(block)
                if count != node["size"]:
                    raise ValueError("DAT incompleto")
                sha = hashlib.sha1(f"blob {count}\0".encode())
                with temporary.open("rb") as stream:
                    for block in iter(lambda: stream.read(262144), b""):
                        sha.update(block)
                if sha.hexdigest() != node["sha"]:
                    raise ValueError("Hash Git DAT non corrispondente")
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        cached_hash = hashlib.sha1(f"blob {target.stat().st_size}\0".encode())
        with target.open("rb") as cached:
            for block in iter(lambda: cached.read(262144), b""):
                cached_hash.update(block)
        if target.stat().st_size != node["size"] or cached_hash.hexdigest() != node["sha"]:
            raise ValueError("Cache DAT modificata: rimuovere il file dalla cache e riprovare")
        hints = {}
        if core == "lr-fbneo":
            for filename, system in [
                ("d_cps1.cpp", "CPS-1"),
                ("d_cps2.cpp", "CPS-2"),
                ("d_cps3.cpp", "CPS-3"),
                ("d_neogeo.cpp", "Neo Geo"),
            ]:
                driver = next(
                    (n for n in tree["tree"] if n["type"] == "blob" and n["path"].endswith("/" + filename)),
                    None,
                )
                if not driver or driver.get("size", 0) > 15_000_000:
                    raise ValueError("Metadati driver ufficiali non disponibili: " + filename)
                cache = folder / (driver["sha"] + ".driver")
                content = (
                    cache.read_bytes()
                    if cache.exists()
                    else http.read(
                        f"https://raw.githubusercontent.com/{repo}/{commit}/" + driver["path"], 15_000_000
                    )
                )
                if hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest() != driver["sha"]:
                    raise ValueError("Hash dei metadati driver non corrispondente")
                cache.write_bytes(content)
                hints.update(driver_hints(content.decode("utf-8-sig"), driver["path"], system))
                service.checkpoint(run_id, {"phase": "Lettura metadati driver " + system})
        imported = CatalogImport(
            source_id="official-" + body.provider,
            name="MAME 0.78" if core == "lr-mame2003" else "FBNeo · " + commit[:7],
            path=str(target),
            format="xml",
            platform="mame-libretro" if core == "lr-mame2003" else "fba",
            core=core,
            version="0.78" if core == "lr-mame2003" else "",
            source_url=url,
            revision=commit,
        )
        result = service.import_catalog(imported, run_id, official=True, hints=hints)
        result.update(metadata_only=True, revision=commit, source_url=url)
        return result
    finally:
        http.close()
