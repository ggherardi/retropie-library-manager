import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from backend.config import EXTENSIONS, PLATFORMS
from backend.paths import digest, reference, within

CUE_FILE = re.compile(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+\S+\s*$', re.IGNORECASE)
DISC = re.compile(r"\s*[\(\[](?:(?:disc|disk|cd)\s*\d+)[\)\]]", re.IGNORECASE)


def linked_files(path: Path, root: Path, stack: set[Path] | None = None) -> list[Path]:
    path = within(path, root)
    stack = set() if stack is None else stack
    if path in stack:
        raise ValueError("Riferimento ciclico M3U")
    if path.suffix.lower() not in {".cue", ".m3u"}:
        return [path]
    stack = stack | {path}
    text = path.read_text(encoding="utf-8-sig")
    names = []
    for line in text.splitlines():
        if path.suffix.lower() == ".cue":
            match = CUE_FILE.match(line)
            if match:
                names.append(match.group(1) or match.group(2))
        elif line.strip() and not line.lstrip().startswith("#"):
            names.append(line.strip())
    if not names:
        raise ValueError("CUE/M3U privo di riferimenti validi")
    result = [path]
    for name in names:
        child = reference(path.parent, name, root)
        if path.suffix.lower() == ".m3u" and child.suffix.lower() not in {".cue", ".chd", ".pbp", ".iso"}:
            raise ValueError("Un M3U deve riferirsi a dischi PS1 CUE/CHD/PBP/ISO")
        result.extend(linked_files(child, root, stack))
    return list(dict.fromkeys(result))


def detect(path: Path, override: str | None) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".m3u":
        return "psx"
    if suffix in {".zip", ".7z", ".bin"}:
        platform = override or next(
            (p.lower() for p in reversed(path.parts[:-1]) if p.lower() in PLATFORMS), None
        )
        if suffix == ".bin" and platform != "megadrive":
            return None
        return platform
    return EXTENSIONS.get(suffix)


def candidate(entrypoints: list[Path], root: Path, platform: str) -> dict:
    paths = list(dict.fromkeys(p for entry in entrypoints for p in linked_files(entry, root)))
    base = Path(os.path.commonpath([str(p.parent) for p in paths]))
    files = []
    for path in paths:
        stat = path.stat()
        sha = digest(path)
        after = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("File cambiato durante la scansione")
        files.append(
            {
                "path": str(path),
                "relative": path.relative_to(base).as_posix(),
                "sha256": sha,
                "size": stat.st_size,
            }
        )
    identity = (
        files[0]["sha256"]
        if len(files) == 1
        else hashlib.sha256(
            json.dumps(sorted((f["relative"], f["sha256"]) for f in files)).encode()
        ).hexdigest()
    )
    title = DISC.sub("", entrypoints[0].stem) if len(entrypoints) > 1 else entrypoints[0].stem
    region = next(
        (r for r in ["Europe", "USA", "Japan", "World"] if r.lower() in title.lower()), "Sconosciuta"
    )
    return {
        "title": title,
        "platform": platform,
        "region": region,
        "format": "multidisc" if len(entrypoints) > 1 else entrypoints[0].suffix[1:].lower(),
        "local_path": str(entrypoints[0]),
        "sha256": identity,
        "files": files,
        "size": sum(f["size"] for f in files),
        "entrypoints": [p.relative_to(base).as_posix() for p in entrypoints],
    }


def scan(root: Path, override: str | None, known: set[str]) -> dict:
    paths = []
    warnings = []
    for directory, dirs, filenames in os.walk(
        root, followlinks=False, onerror=lambda e: warnings.append(str(e))
    ):
        dirs[:] = [
            d
            for d in dirs
            if not (Path(directory) / d).is_symlink()
            and (Path(directory) / d).resolve() == Path(directory) / d
        ]
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if not path.is_symlink():
                paths.append(path)
    paths.sort(key=lambda p: ({".m3u": 0, ".cue": 1}.get(p.suffix.lower(), 2), str(p).lower()))
    consumed: set[Path] = set()
    candidates: list[dict[str, Any]] = []
    for path in paths:
        if path in consumed:
            continue
        platform = detect(path, override)
        if not platform:
            if path.suffix.lower() in {".bin", ".zip", ".7z"}:
                warnings.append(
                    f"{path.name}: formato ambiguo o BIN senza CUE. Specificare la console o fornire il CUE."
                )
            continue
        try:
            entries = [path]
            if (
                platform == "psx"
                and path.suffix.lower() in {".cue", ".chd", ".iso", ".pbp"}
                and DISC.search(path.stem)
            ):
                entries = sorted(
                    [
                        p
                        for p in paths
                        if p not in consumed
                        and DISC.search(p.stem)
                        and p.parent == path.parent
                        and p.suffix.lower() == path.suffix.lower()
                        and DISC.sub("", p.stem) == DISC.sub("", path.stem)
                    ],
                    key=lambda p: int(re.findall(r"(?:disc|disk|cd)\s*(\d+)", p.stem, re.I)[0]),
                )
            item = candidate(entries, root, platform)
            consumed.update(Path(f["path"]) for f in item["files"])
            item["id"] = len(candidates)
            item["duplicate"] = item["sha256"] in known
            known.add(item["sha256"])
            candidates.append(item)
        except (OSError, ValueError, UnicodeError) as exc:
            warnings.append(f"{path.name}: {exc}")
    return {"root": str(root), "candidates": candidates, "warnings": warnings, "scanned_files": len(paths)}
