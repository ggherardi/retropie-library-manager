"""Content and active DAT identification for the unified installation pipeline."""

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

from sqlalchemy import bindparam, select, text

from backend.acquisition import record
from backend.arcade_archives import inspect_archive, matches, validate_set
from backend.content_checks import disc_check, format_check
from backend.db import CatalogEntry, CatalogSource, DiscoveryEntry, Game
from backend.import_service import logical_files
from backend.paths import allowed, digest
from backend.scanner import DISC, candidate


def enumerate_files(paths, roots, recursive=True):
    result = set()
    for value in paths:
        path = allowed(value, roots)
        if path.is_file():
            result.add(path)
        elif path.is_dir():
            for directory, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    name
                    for name in dirs
                    if recursive
                    and not (Path(directory) / name).is_symlink()
                    and (Path(directory) / name).resolve() == Path(directory) / name
                ]
                for name in files:
                    child = Path(directory) / name
                    if not child.is_symlink():
                        result.add(allowed(str(child), roots))
                    if len(result) > 20000:
                        raise ValueError("Selezionare al massimo 20.000 file per batch")
    return sorted(result, key=lambda p: ({".m3u": 0, ".cue": 1}.get(p.suffix.lower(), 2), str(p).casefold()))


class Identifier:
    def __init__(self, sessions):
        self.sessions = sessions

    def archive(self, path, roots, checkpoint, selected_uid="", mode="non-merged"):
        before = path.stat()
        inventory = inspect_archive(path, checkpoint)
        stat = path.stat()
        if (before.st_size, before.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
            raise ValueError("Archivio modificato durante l'identificazione")
        shared = {
            (str(path.resolve()), stat.st_size, stat.st_mtime_ns): (inventory, digest(path, checkpoint))
        }
        hashes = list({x["sha1"] for x in inventory.values()})[:500]
        crcs = list({x["crc"] for x in inventory.values()})[:500]
        with self.sessions() as db:
            if selected_uid:
                entries = list(
                    db.scalars(
                        select(CatalogEntry)
                        .join(CatalogSource, CatalogSource.active_run == CatalogEntry.run_id)
                        .where(CatalogEntry.uid == selected_uid)
                    )
                )
            else:
                query = text("""SELECT DISTINCT e.id FROM catalog_entries e
                    JOIN catalog_sources s ON s.active_run=e.run_id, json_each(e.components) c
                    WHERE json_extract(c.value,'$.sha1') IN :hashes
                       OR json_extract(c.value,'$.crc') IN :crcs""").bindparams(
                    bindparam("hashes", expanding=True), bindparam("crcs", expanding=True)
                )
                ids = list(db.scalars(query, {"hashes": hashes, "crcs": crcs}))
                entries = (
                    list(db.scalars(select(CatalogEntry).where(CatalogEntry.id.in_(ids)))) if ids else []
                )
            # Common BIOS chips are dependencies, not evidence that unrelated games match.
            bios_parts: dict[str, set[tuple[int | None, str]]] = {}
            for bios in db.scalars(
                select(CatalogEntry).where(
                    CatalogEntry.run_id.in_({e.run_id for e in entries}), CatalogEntry.kind == "bios"
                )
            ):
                bios_parts.setdefault(bios.run_id, set()).update(
                    (p["size"], p.get("sha1") or p.get("crc")) for p in bios.components
                )
            ranked = []
            for entry in entries:
                if entry.kind != "game":
                    continue
                parts = [
                    p
                    for p in entry.components
                    if p["kind"] == "rom"
                    and not p["optional"]
                    and (p["size"], p.get("sha1") or p.get("crc")) not in bios_parts.get(entry.run_id, set())
                ]
                matched = sum(any(matches(p, v) for v in inventory.values()) for p in parts)
                if matched:
                    ranked.append((matched, entry))
            ranked.sort(key=lambda pair: -pair[0])
            # Keep tied variants; never silently auto-select when the shortlist is truncated.
            ranked = ranked[:24]
            candidates = []
            for matched, entry in ranked:
                checkpoint()
                source = db.get(CatalogSource, entry.source_id)
                catalog = {}
                pending = [entry.name]
                while pending:
                    name = pending.pop()
                    if name in catalog:
                        continue
                    item = db.scalar(
                        select(CatalogEntry).where(
                            CatalogEntry.run_id == source.active_run, CatalogEntry.name == name
                        )
                    )
                    if item:
                        value = record(item)
                        catalog[name] = value
                        pending.extend(
                            filter(None, [item.parent, item.romof, *item.details.get("dependencies", [])])
                        )
                archives = {}
                for name in catalog:
                    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,150}", name) or name in {".", ".."}:
                        continue
                    for extension in (".zip", ".7z"):
                        sibling = path.parent / (name + extension)
                        if sibling.is_file():
                            archives[name] = allowed(str(sibling), roots)
                    if name not in archives:
                        for game in db.scalars(select(Game).where(Game.format.in_(["zip", "7z"]))):
                            if Path(game.local_path).stem == name:
                                try:
                                    archives[name] = allowed(game.local_path, roots)
                                except ValueError:
                                    pass
                reports = []
                for selected_mode in (
                    [mode] if selected_uid else ["non-merged", "full-non-merged", "split", "merged"]
                ):
                    main = entry.parent if selected_mode == "merged" and entry.parent else entry.name
                    report = validate_set(
                        record(entry), catalog, {**archives, main: path}, selected_mode, checkpoint, shared
                    )
                    report.update(
                        source_id=source.id,
                        source_version=source.config.get("version"),
                        core=source.config.get("core"),
                        entry_title=entry.title,
                    )
                    reports.append(report)
                    if report["launchable"]:
                        break
                best = min(reports, key=lambda r: (not r["launchable"], len(r["problems"])))
                candidates.append(
                    {
                        "uid": entry.uid,
                        "title": entry.title,
                        "platform": entry.platform,
                        "source_id": source.id,
                        "source_sha": source.sha256,
                        "core": source.config.get("core"),
                        "matched_components": matched,
                        "report": best,
                        "mode": best["mode"],
                        "basis": "Dimensioni e hash dei membri confrontati con il DAT attivo",
                    }
                )
        complete = [c for c in candidates if c["report"]["launchable"]]
        chosen = complete[0] if len(complete) == 1 and len(ranked) < 24 else None
        return {
            "candidates": candidates,
            "chosen": chosen,
            "member_count": len(inventory),
            "reason": ""
            if chosen
            else "Nessun set completo univoco. Confrontare componenti, variante e versione del DAT; la scelta non aggira la validazione.",
        }

    def identify(self, path, root, roots, paths, checkpoint=lambda: None, decision=None):
        initial = path.stat()
        decision = decision or {}
        check = format_check(path)
        info = {
            "title": path.stem,
            "platform": check["platform"],
            "format": path.suffix[1:].lower(),
            "catalog_uid": "",
            "match": "proposed",
            "validation": "unverified",
            "dependencies": [],
            "basis": check["basis"],
            "reason": check["reason"],
            "choices": check["choices"],
            "kind": check["kind"],
        }
        if check["kind"] in {"bios", "ignored"}:
            return {"status": "ignored", "identification": info, "candidate": {}, "consumed": [path]}
        if check["kind"] == "archive":
            arcade = self.archive(
                path,
                roots,
                checkpoint,
                decision.get("entry_uid", ""),
                decision.get("archive_mode", "non-merged"),
            )
            info.update(arcade)
            chosen = arcade["chosen"]
            if not chosen:
                candidates = arcade["candidates"]
                info["size"] = path.stat().st_size
                if candidates and (
                    len(candidates) == 1
                    or candidates[0]["matched_components"] > candidates[1]["matched_components"]
                ):
                    proposal = candidates[0]
                    info.update(
                        title=proposal["title"],
                        platform=proposal["platform"],
                        catalog_uid=proposal["uid"],
                        validation=proposal["report"]["status"],
                    )
                return {
                    "status": "awaiting_decision",
                    "identification": info,
                    "candidate": {},
                    "consumed": [path],
                }
            check.update(valid=True, platform=chosen["platform"])
            info.update(
                title=chosen["title"],
                platform=chosen["platform"],
                catalog_uid=chosen["uid"],
                match="verified",
                validation="complete",
                dependencies=chosen["report"]["bios"],
                basis=chosen["basis"],
            )
        entries = [path]
        if check["platform"] == "psx" and path.suffix.lower() != ".m3u":
            if DISC.search(path.stem):
                entries = sorted(
                    [
                        p
                        for p in paths
                        if p.parent == path.parent
                        and p.suffix.lower() == path.suffix.lower()
                        and DISC.sub("", p.stem) == DISC.sub("", path.stem)
                    ],
                    key=lambda p: int(re.findall(r"(?:disc|disk|cd)\s*(\d+)", p.stem, re.I)[0]),
                )
        item = candidate(entries, root, check["platform"] or "unknown", checkpoint)
        if info.get("chosen"):
            report = info["chosen"]["report"]
            if report["archives"][report["main_archive"]]["sha256"] != item["sha256"]:
                raise ValueError("Archivio cambiato dopo il confronto DAT: ripetere l'analisi")
        consumed = [Path(f["path"]) for f in item["files"]]
        with self.sessions() as db:
            known = db.scalar(select(Game).where(Game.sha256 == item["sha256"]))
            if len(item["files"]) == 1 and check["kind"] != "archive":
                sha1 = hashlib.sha1()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        checkpoint()
                        sha1.update(block)
                ids = list(
                    db.scalars(
                        text("""SELECT DISTINCT e.id FROM catalog_entries e
                    JOIN catalog_sources s ON s.active_run=e.run_id, json_each(e.components) c
                    WHERE json_array_length(e.components)=1 AND json_extract(c.value,'$.sha1')=:sha
                    AND json_extract(c.value,'$.size')=:size
                    AND e.platform NOT IN ('arcade','neogeo','mame-libretro','fba','psx')"""),
                        {"sha": sha1.hexdigest(), "size": item["size"]},
                    )
                )
                cart_entries = (
                    list(db.scalars(select(CatalogEntry).where(CatalogEntry.id.in_(ids)))) if ids else []
                )
                if len({(c.title, c.platform, c.kind) for c in cart_entries}) == 1:
                    entry = cart_entries[0]
                    if entry.kind != "game":
                        info.update(
                            kind=entry.kind,
                            reason="BIOS/dispositivo identificato tramite DAT e SHA-1",
                            catalog_uid=entry.uid,
                        )
                        return {
                            "status": "ignored",
                            "identification": info,
                            "candidate": {},
                            "consumed": consumed,
                        }
                    if not check["platform"] or check["platform"] == entry.platform:
                        check.update(valid=True, platform=entry.platform)
                        info.update(
                            title=entry.title,
                            platform=entry.platform,
                            catalog_uid=entry.uid,
                            match="verified",
                            basis="SHA-1 e dimensione corrispondenti al DAT attivo",
                        )
            if not known and check["platform"] == "psx":
                same = [
                    g
                    for g in db.scalars(select(Game).where(Game.platform == "psx"))
                    if logical_files(g.files) == logical_files(item["files"])
                ]
                known = same[0] if len(same) == 1 else None
            discovery = list(
                db.scalars(
                    select(DiscoveryEntry).where(
                        DiscoveryEntry.sha256 == item["sha256"], DiscoveryEntry.available.is_(True)
                    )
                )
            )
            exact = known or (discovery[0] if len(discovery) == 1 else None)
            if exact and (not check["platform"] or exact.platform == check["platform"]):
                check.update(valid=True, platform=exact.platform)
                info.update(
                    title=exact.title,
                    platform=exact.platform,
                    match="verified",
                    basis="SHA-256 identico a " + ("libreria locale" if known else "fonte Discovery"),
                )
            info["duplicate"] = bool(known)
            info["existing_game_id"] = known.id if known else None
            if known:
                item["existing_game_id"] = known.id
        raw_platforms = {"pcengine", "atari2600", "sg-1000", "ngp", "ngpc"}
        selected_platform = decision.get("platform")
        if (
            not check["valid"]
            and selected_platform in raw_platforms
            and selected_platform in check["choices"]
        ):
            if item["size"] < 1024 or item["size"] > 8 * 1024**2 or item["size"] % 512:
                raise ValueError("Dimensione del formato grezzo non valida: selezione manuale rifiutata")
            check.update(valid=True, platform=selected_platform)
            info.update(
                platform=selected_platform,
                basis="Piattaforma dichiarata dall'operatore; dimensione e SHA-256 verificati, compatibilità non verificata",
            )
        if not check["valid"]:
            return {
                "status": "awaiting_decision",
                "identification": info,
                "candidate": item,
                "consumed": consumed,
            }
        if decision.get("platform") and decision["platform"] != check["platform"]:
            raise ValueError("La piattaforma scelta non corrisponde al contenuto verificato")
        if check["platform"] == "psx":
            for entry in entries:
                if entry.suffix.lower() == ".bin":
                    raise ValueError("BIN PS1 senza CUE: selezionare il descrittore e tutte le tracce")
                disc_check(entry, root)
            for file in consumed:
                if file.suffix.lower() == ".chd":
                    if info["match"] != "verified" and decision.get("platform") != "psx":
                        info.update(
                            choices=["psx"],
                            reason="CHD è un contenitore multipiattaforma: confermare PlayStation solo se nota dalla fonte. Seguiranno verifica chdman, core e BIOS.",
                        )
                        return {
                            "status": "awaiting_decision",
                            "identification": info,
                            "candidate": item,
                            "consumed": consumed,
                        }
                    chdman = shutil.which("chdman")
                    if not chdman:
                        info["reason"] = (
                            "CHD: serve chdman nel PATH per verificare l'integrità, oltre al supporto del core"
                        )
                        return {
                            "status": "awaiting_decision",
                            "identification": info,
                            "candidate": item,
                            "consumed": consumed,
                        }
                    completed = subprocess.run(
                        [chdman, "verify", "-i", str(file)],
                        capture_output=True,
                        timeout=300,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    if completed.returncode:
                        raise ValueError("Verifica integrità CHD fallita")
                if file.suffix.lower() == ".pbp" and info["match"] != "verified":
                    info["reason"] = (
                        "PBP PS1 rilevato: serve un hash verificato dalla fonte per attestare la completezza del contenuto compresso"
                    )
                    return {
                        "status": "awaiting_decision",
                        "identification": info,
                        "candidate": item,
                        "consumed": consumed,
                    }
        item.update(
            title=info["title"] if info["match"] == "verified" else item["title"], platform=check["platform"]
        )
        info.update(
            title=item["title"],
            platform=item["platform"],
            validation="complete",
            basis=info["basis"] or check["basis"],
            reason="",
        )
        if decision.get("title"):
            title = decision["title"].strip()
            if not title or not decision.get("confirmed_title") or re.fullmatch(r"(?i)rlm-[a-f0-9]+", title):
                raise ValueError("Confermare un titolo leggibile e verificato")
            item["title"] = info["title"] = title
            info.update(match="verified", basis=info["basis"] + "; titolo confermato dall'operatore")
        if re.fullmatch(r"(?i)rlm-[a-f0-9]+", item["title"]):
            info["reason"] = (
                "Identificativo tecnico: inserire un titolo verificato presso la fonte, senza inventarlo"
            )
            return {
                "status": "awaiting_decision",
                "identification": info,
                "candidate": item,
                "consumed": consumed,
            }
        final = path.stat()
        if (initial.st_size, initial.st_mtime_ns) != (final.st_size, final.st_mtime_ns):
            raise ValueError("File modificato durante l'identificazione")
        return {"status": "ready", "identification": info, "candidate": item, "consumed": consumed}
