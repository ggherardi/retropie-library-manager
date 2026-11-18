"""Expand console containers while keeping identified arcade sets in their original form."""

from pathlib import Path

from sqlalchemy import select

from backend.archive_import import ARCHIVES, ArchiveStore, Budget, inventory
from backend.content_checks import format_check
from backend.db import CatalogEntry, CatalogPreference, CatalogSource
from backend.identification import enumerate_files
from backend.scanner import CUE_FILE

CONSOLE_MEMBERS = {
    ".nes",
    ".fds",
    ".sfc",
    ".smc",
    ".gen",
    ".md",
    ".smd",
    ".sms",
    ".gg",
    ".gb",
    ".gbc",
    ".gba",
    ".pce",
    ".a26",
    ".a78",
    ".sg",
    ".ngp",
    ".ngc",
    ".cue",
    ".m3u",
    ".iso",
    ".chd",
    ".pbp",
    ".ecm",
    ".ape",
}


def review(path, reason, **details):
    return {
        "status": "awaiting_decision",
        "candidate": {},
        "consumed": [path],
        "identification": {
            "title": path.stem,
            "platform": "",
            "format": path.suffix[1:].lower(),
            "kind": "archive",
            "reason": reason,
            "validation": "unverified",
            **details,
        },
    }


class ArchiveAnalyzer:
    def __init__(self, identifier, data):
        self.identifier = identifier
        self.store = ArchiveStore(data)

    def analyze(self, path, root, roots, checkpoint=lambda: None):
        budget = Budget(checkpoint)
        result = self.expand(path, root, roots, budget, 0, [])
        self.variants(result)
        return result

    def expand(self, path, root, roots, budget, depth, chain):
        entries = inventory(path, budget.check)
        if depth > 3:
            raise ValueError("Limite di profondità degli archivi annidati superato")
        suffixes = {Path(e["name"]).suffix.lower() for e in entries if not e["directory"]}
        if not suffixes.intersection(CONSOLE_MEMBERS | ARCHIVES):
            check = format_check(path)
            if check["kind"] == "bios":
                result = self.identifier.identify(path, root, roots, [path], budget.check)
                return [(path, result)]
            arcade = self.identifier.archive(path, roots, budget.check)
            if arcade["candidates"]:
                result = self.identifier.identify(
                    path, root, roots, [path], budget.check, archive_result=arcade
                )
                result["identification"]["archive"] = {
                    "original": str(path),
                    "preserved": True,
                    "members": len(entries),
                    "extracted": False,
                    "chain": chain,
                }
                return [(path, result)]
        prepared, report = self.store.prepare(path, entries, budget, depth)
        provenance = {
            "original": str(path),
            "sha256": report["archive_sha256"],
            "members": report["members"],
            "expanded_bytes": report["expanded_bytes"],
            "extracted": True,
            "preserved": True,
            "chain": chain,
            "contents": [e["name"] for e in entries][:200],
        }
        prepared_roots = [*roots, str(self.store.root)]
        paths = enumerate_files([str(prepared)], prepared_roots)
        encoded = [p for p in paths if p.suffix.lower() in {".ecm", ".ape"}]
        encoded_result = None
        if encoded and not any(p.suffix.lower() in {".cue", ".m3u", ".iso", ".chd"} for p in paths):
            formats = sorted({p.suffix[1:].upper() for p in encoded})
            signatures = {}
            for p in encoded:
                with p.open("rb") as stream:
                    signatures[p.name] = stream.read(4).hex()
            # Only inspect sibling names in the already authorized source directory.
            associated = [
                p.name
                for p in path.parent.iterdir()
                if p.is_file() and not p.is_symlink() and p.suffix.lower() in {".cue", ".m3u", ".ape", ".ecm"}
            ][:200]
            message = (
                "Contenuto compresso "
                + ", ".join(formats)
                + ": "
                + ", ".join(p.name for p in encoded)
                + ". Decodifica ECM/APE non supportata; nessuna immagine PS1 completa verificata. "
                + "Manca nell'archivio un descrittore CUE/M3U con ordine, tipo e indici delle tracce. "
                + "Occorre una copia completa in BIN/CUE, ISO o CHD supportato; l'app la prepara automaticamente. "
                + "Non vengono inventati CUE o indici audio."
            )
            issue = review(
                path,
                message,
                archive=provenance,
                unsupported_formats=formats,
                missing_components=["Descrittore CUE/M3U del disco"],
                associated_files=associated,
                signatures=signatures,
            )
            other_games = any(
                p not in encoded
                and p.suffix.lower() in ((CONSOLE_MEMBERS | ARCHIVES | {".bin"}) - {".ecm", ".ape"})
                for p in paths
            )
            if not other_games:
                return [(path, issue)]
            encoded_result = (encoded[0], issue)
        consumed = set(encoded) if encoded_result else set()
        children = [encoded_result] if encoded_result else []
        ignored = []
        for child in paths:
            budget.check()
            if child in consumed:
                continue
            if child.suffix.lower() in ARCHIVES:
                try:
                    children.extend(
                        self.expand(child, prepared, prepared_roots, budget, depth + 1, [*chain, str(path)])
                    )
                except ValueError as exc:
                    children.append((child, review(child, str(exc), archive=provenance)))
                consumed.add(child)
                continue
            try:
                result = self.identifier.identify(child, prepared, prepared_roots, paths, budget.check)
            except (ValueError, OSError, UnicodeError) as exc:
                message = (
                    "Componente mancante: " + Path(exc.filename).name
                    if isinstance(exc, FileNotFoundError) and exc.filename
                    else str(exc)
                )
                result = review(child, message)
                if child.suffix.lower() == ".cue":
                    for line in child.read_text(encoding="utf-8-sig").splitlines():
                        match = CUE_FILE.match(line)
                        if match:
                            name = (match.group(1) or match.group(2)).replace("\\", "/")
                            consumed.update(p for p in paths if p == child.parent / name)
            consumed.update(result.pop("consumed"))
            result["identification"]["archive"] = provenance
            result["consumed"] = [child]
            if result["status"] == "ignored":
                ignored.append(
                    {
                        "name": child.relative_to(prepared).as_posix(),
                        "reason": result["identification"]["reason"],
                    }
                )
            else:
                children.append((child, result))
        if not children:
            parent = review(
                path,
                "Nessun gioco riconoscibile: l'archivio contiene soltanto documenti, BIOS o formati non supportati.",
                archive=provenance,
                ignored_members=ignored,
            )
        else:
            parent = {
                "status": "prepared",
                "candidate": {},
                "consumed": [path],
                "identification": {
                    "title": path.name,
                    "kind": "archive_container",
                    "archive": provenance,
                    "reason": f"Archivio preparato automaticamente: {len(children)} elementi da analizzare/installare.",
                    "ignored_members": ignored,
                },
            }
        return [(path, parent), *children]

    def variants(self, rows):
        groups: dict[tuple[str, str], list] = {}
        with self.identifier.sessions() as db:
            for path, result in rows:
                uid = result["identification"].get("catalog_uid")
                if result["status"] != "ready" or not uid:
                    continue
                entry = db.scalar(
                    select(CatalogEntry)
                    .join(CatalogSource, CatalogSource.active_run == CatalogEntry.run_id)
                    .where(CatalogEntry.uid == uid)
                )
                if entry and entry.family:
                    groups.setdefault((entry.source_id, entry.family), []).append((path, result, entry))
            preferences = {p.preferred_uid for p in db.scalars(select(CatalogPreference))}
        for members in groups.values():
            if len(members) < 2 or len({m[1]["candidate"]["sha256"] for m in members}) < 2:
                continue
            preferred = [m for m in members if m[2].uid in preferences]
            options = [{"source": str(p), "title": r["identification"]["title"]} for p, r, _ in members]
            for index, (path, result, _) in enumerate(members):
                if len(preferred) == 1:
                    if path != preferred[0][0]:
                        result["status"] = "ignored"
                        result["identification"]["reason"] = (
                            "Conservata nell'archivio; applicata la variante preferita configurata"
                        )
                else:
                    result["status"] = "awaiting_decision" if index == 0 else "ignored"
                    result["identification"].update(
                        variants=options,
                        reason="Questo archivio contiene più versioni della stessa famiglia verificata. Quale vuoi installare?",
                    )
