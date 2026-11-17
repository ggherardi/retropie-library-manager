"""Versioned catalogs and evidence-based library intelligence, isolated from acquisition rights."""

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import delete, exists, func, insert, select, text, update

from backend.acquisition import fingerprint, record
from backend.arcade_archives import validate_set
from backend.catalog_formats import records
from backend.config import ARCADE_PLATFORMS, PLATFORMS
from backend.core_profiles import PROFILES, audit_cores, compatible, configured_core
from backend.db import (
    ArcadeValidation,
    CatalogEntry,
    CatalogPreference,
    CatalogRun,
    CatalogSource,
    CoreBinding,
    Device,
    DiscoveryEntry,
    Game,
    GameInsight,
    Setting,
    SyncPresence,
    SyncRun,
    now,
)
from backend.intelligence_schemas import (
    BindCore,
    CatalogFilters,
    CatalogImport,
    CatalogMatch,
    CorePreference,
    InsightInput,
    OfficialCatalog,
    PreferredInput,
    ValidateInput,
)
from backend.official_catalogs import fetch_catalog
from backend.paths import allowed, digest, local_path
from backend.remote_fs import rpc

logger = logging.getLogger("rlm")
ACTIVE = {"queued", "running", "cancelling"}


class Cancelled(Exception):
    pass


def active_entries():
    return select(CatalogEntry).join(CatalogSource, CatalogSource.active_run == CatalogEntry.run_id)


class Intelligence:
    def __init__(self, sessions, data_dir, lock, devices):
        self.sessions = sessions
        self.data_dir = data_dir
        self.lock = lock
        self.devices = devices
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="library-intelligence")
        self.stop = threading.Event()
        self.audit = audit_cores
        self.router = self.routes()

    def start(self):
        with self.sessions.begin() as db:
            for run in db.scalars(select(CatalogRun).where(CatalogRun.status.in_(ACTIVE))):
                run.status = "failed"
                run.error = "Operazione interrotta. Ripetere; il catalogo precedente è conservato."
            db.execute(
                delete(CatalogEntry).where(CatalogEntry.run_id.not_in(select(CatalogSource.active_run)))
            )
            # Preserve verified synchronization history from Increment 3, only for identical files.
            for prior in db.scalars(
                select(SyncRun).where(SyncRun.status == "completed").order_by(SyncRun.created_at)
            ):
                for item in prior.plan.get("manifest", {}).get("games", []):
                    game = db.get(Game, item.get("id"))
                    expected = {f["sha256"] for f in item.get("files", [])}
                    if not game or not expected or expected != {f["sha256"] for f in game.files}:
                        continue
                    existing = db.scalar(
                        select(SyncPresence).where(
                            SyncPresence.game_id == game.id, SyncPresence.device_id == prior.device_id
                        )
                    )
                    if not existing:
                        db.add(
                            SyncPresence(
                                game_id=game.id,
                                device_id=prior.device_id,
                                sha256=game.sha256,
                                run_id=prior.id,
                                checked_at=prior.created_at,
                            )
                        )

    def shutdown(self):
        self.stop.set()
        self.pool.shutdown(wait=True)

    def roots(self):
        with self.sessions() as db:
            setting = db.get(Setting, "library")
            return [
                *(setting.value.get("import_roots", []) if setting else []),
                str(self.data_dir / "catalogs"),
            ]

    def checkpoint(self, run_id, progress=None):
        if self.stop.is_set():
            raise Cancelled()
        with self.sessions() as db:
            run = db.get(CatalogRun, run_id)
            if run.status == "cancelling":
                raise Cancelled()
        if progress is not None:
            with self.sessions.begin() as db:
                db.get(CatalogRun, run_id).progress = progress

    def queue(self, kind, operation, source_id=""):
        run_id = str(uuid4())
        with self.sessions.begin() as db:
            db.add(CatalogRun(id=run_id, kind=kind, source_id=source_id))

        def work():
            try:
                self.checkpoint(run_id)
                with self.sessions.begin() as db:
                    db.get(CatalogRun, run_id).status = "running"
                result = operation(run_id)
                with self.sessions.begin() as db:
                    run = db.get(CatalogRun, run_id)
                    run.status = "completed"
                    run.result = result
            except Exception as exc:
                logger.warning("Intelligence %s: %s", run_id, str(exc))
                with self.sessions.begin() as db:
                    run = db.get(CatalogRun, run_id)
                    run.status = "cancelled" if isinstance(exc, Cancelled) else "failed"
                    run.error = (
                        "Annullato: il catalogo precedente è conservato"
                        if isinstance(exc, Cancelled)
                        else str(exc)
                    )
                    if kind == "catalog_import":
                        source = db.get(CatalogSource, source_id)
                        if not source or source.active_run != run_id:
                            db.execute(delete(CatalogEntry).where(CatalogEntry.run_id == run_id))

        self.pool.submit(work)
        return {"id": run_id, "status": "queued"}

    def import_catalog(self, body, run_id, official=False, hints=None):
        started = time.perf_counter()
        path = allowed(body.path, self.roots())
        initial = path.stat()
        file_sha = digest(path)
        config = body.model_dump(exclude={"path", "source_id", "name"})
        config["official_verified"] = official
        config["parser_version"] = 2
        config["driver_metadata_sha"] = fingerprint(hints or {})
        with self.sessions() as db:
            old = db.get(CatalogSource, body.source_id)
        if (
            old
            and old.sha256 == file_sha
            and all(old.config.get(k) == v for k, v in config.items() if k != "version" or v)
        ):
            return {
                "unchanged_file": True,
                "records": self.source_count(old.active_run),
                "sha256": file_sha,
                "seconds": time.perf_counter() - started,
            }
        header: dict[str, Any] = {}
        buffer: list[dict] = []
        count = 0
        duplicate_count = 0
        changes = {"added": 0, "changed": 0, "unchanged": 0}

        def flush():
            nonlocal duplicate_count
            self.checkpoint(
                run_id, {"records": count, "bytes": initial.st_size, "phase": "Importazione in staging"}
            )
            unique: dict[str, dict] = {}
            for row in buffer:
                if row["name"] in unique:
                    if row["payload_sha"] != unique[row["name"]]["payload_sha"]:
                        raise ValueError("Record duplicato con contenuti differenti: " + row["name"])
                    duplicate_count += 1
                unique[row["name"]] = row
            with self.sessions.begin() as db:
                existing = dict(
                    db.execute(
                        select(CatalogEntry.name, CatalogEntry.payload_sha).where(
                            CatalogEntry.run_id == run_id, CatalogEntry.name.in_(unique)
                        )
                    ).all()
                )
                previous = dict(
                    db.execute(
                        select(CatalogEntry.name, CatalogEntry.payload_sha).where(
                            CatalogEntry.run_id == (old.active_run if old else ""),
                            CatalogEntry.name.in_(unique),
                        )
                    ).all()
                )
                new = []
                for name, row in unique.items():
                    if name in existing:
                        if row["payload_sha"] != existing[name]:
                            raise ValueError("Record duplicato in conflitto: " + name)
                        duplicate_count += 1
                        continue
                    changes[
                        "added"
                        if name not in previous
                        else "unchanged"
                        if previous[name] == row["payload_sha"]
                        else "changed"
                    ] += 1
                    new.append(
                        {
                            **row,
                            "run_id": run_id,
                            "source_id": body.source_id,
                            "uid": fingerprint([body.source_id, name]),
                        }
                    )
                if new:
                    db.execute(insert(CatalogEntry), new)
            buffer.clear()

        for row in records(path, body.format, body.platform, header, hints):
            count += 1
            if count > 500000:
                raise ValueError("Limite di 500.000 record per catalogo")
            buffer.append(row)
            if len(buffer) >= 250:
                flush()
        if buffer:
            flush()
        if not count:
            raise ValueError("Catalogo privo di record compatibili")
        if (path.stat().st_size, path.stat().st_mtime_ns) != (initial.st_size, initial.st_mtime_ns) or digest(
            path
        ) != file_sha:
            raise ValueError("Catalogo modificato durante la lettura")
        self.checkpoint(run_id, {"records": count, "phase": "Verifica parent e pubblicazione"})
        with self.sessions.begin() as db:
            parents = dict(
                db.execute(
                    select(CatalogEntry.name, CatalogEntry.parent).where(CatalogEntry.run_id == run_id)
                ).all()
            )
            for name, parent in parents.items():
                chain = {name}
                family = parent or name
                while parents.get(family):
                    if family in chain:
                        raise ValueError("Parent/clone ciclico: " + name)
                    chain.add(family)
                    family = parents[family]
                if family != (parent or name):
                    db.execute(
                        update(CatalogEntry)
                        .where(CatalogEntry.run_id == run_id, CatalogEntry.name == name)
                        .values(family=family)
                    )
            source = db.get(CatalogSource, body.source_id)
            if not source:
                source = CatalogSource(id=body.source_id, name=body.name)
                db.add(source)
            config["header"] = {k: str(v)[:2000] for k, v in header.items()}
            if not config["version"]:
                config["version"] = str(header.get("version") or header.get("build") or "")[:300]
            source.name = body.name
            source.config = config
            source.active_run = run_id
            source.sha256 = file_sha
            source.updated_at = now()
            # Atomic pointer switch. Interrupted staging is never exposed to readers.
            run = db.get(CatalogRun, run_id)
            if run.status == "cancelling" or self.stop.is_set():
                raise Cancelled()
        with self.sessions.begin() as db:
            db.execute(
                delete(CatalogEntry).where(
                    CatalogEntry.source_id == body.source_id, CatalogEntry.run_id != run_id
                )
            )
        return {
            "records": count - duplicate_count,
            "duplicates": duplicate_count,
            **changes,
            "sha256": file_sha,
            "header": header,
            "seconds": round(time.perf_counter() - started, 3),
        }

    def source_count(self, run_id):
        with self.sessions() as db:
            return db.scalar(
                select(func.count()).select_from(CatalogEntry).where(CatalogEntry.run_id == run_id)
            )

    def source(self, db, source_id):
        source = db.get(CatalogSource, source_id)
        if not source or not source.active_run:
            raise ValueError("Catalogo non disponibile")
        return source

    def validation_view(self, db, game):
        validation = db.get(ArcadeValidation, game.id)
        if not validation:
            return None
        result = record(validation)
        source = db.get(CatalogSource, validation.report.get("source_id", ""))
        if not source or source.sha256 != validation.source_sha or validation.archive_sha != game.sha256:
            result["status"] = "stale"
        return result

    def validate(self, body, run_id):
        with self.sessions() as db:
            source = self.source(db, body.source_id)
            games = list(db.scalars(select(Game).where(Game.id.in_(body.game_ids))))
            if len(games) != len(set(body.game_ids)):
                raise ValueError("Giochi non trovati")
            # Compact dependency map; payloads for unrelated sets stay in SQLite.
            lookup = {
                name: entry_id
                for name, entry_id in db.execute(
                    select(CatalogEntry.name, CatalogEntry.id).where(CatalogEntry.run_id == source.active_run)
                )
            }
            files = list(db.scalars(select(Game).where(Game.platform.in_(ARCADE_PLATFORMS))))
        archives: dict[str, Path] = {}
        ambiguous = set()
        for game in files:
            name = Path(game.local_path).stem
            if name in archives and archives[name] != Path(game.local_path):
                ambiguous.add(name)
            archives[name] = Path(game.local_path)
        results = []
        for index, game in enumerate(games):
            self.checkpoint(run_id, {"done": index, "total": len(games), "file": game.title})
            with self.sessions() as db:
                selected = (
                    db.scalar(
                        active_entries().where(
                            CatalogEntry.uid == body.entry_uid, CatalogEntry.source_id == source.id
                        )
                    )
                    if body.entry_uid and len(games) == 1
                    else db.get(CatalogEntry, lookup.get(Path(game.local_path).stem, -1))
                )
                if not selected:
                    results.append(
                        {
                            "game_id": game.id,
                            "status": "unmatched",
                            "reason": "Nome tecnico non trovato; scegliere esplicitamente un record DAT",
                        }
                    )
                    continue
                catalog = {}
                pending = [selected.name]
                while pending:
                    name = pending.pop()
                    if name in catalog or name not in lookup:
                        continue
                    value = record(db.get(CatalogEntry, lookup[name]))
                    catalog[name] = value
                    pending.extend(
                        filter(
                            None, [value["parent"], value["romof"], *value["details"].get("dependencies", [])]
                        )
                    )
            if game.sha256 != digest(Path(game.local_path)):
                raise ValueError("File locale modificato: " + game.title)
            available = {k: v for k, v in archives.items() if k not in ambiguous}
            # An explicit match may select a renamed local archive; retain the original export name separately.
            main_name = selected.parent if body.mode == "merged" and selected.parent else selected.name
            available[main_name] = Path(game.local_path)
            report = validate_set(
                catalog[selected.name], catalog, available, body.mode, lambda: self.checkpoint(run_id)
            )
            report.update(
                source_id=source.id,
                source_version=source.config.get("version"),
                core=source.config.get("core"),
                entry_title=selected.title,
            )
            with self.sessions.begin() as db:
                if self.source(db, source.id).sha256 != source.sha256:
                    raise ValueError("DAT cambiato; ripetere la validazione")
                db.merge(
                    ArcadeValidation(
                        game_id=game.id,
                        catalog_uid=selected.uid,
                        source_sha=source.sha256,
                        archive_sha=game.sha256,
                        mode=body.mode,
                        status=report["status"],
                        report=report,
                        checked_at=now(),
                    )
                )
                insight = db.get(GameInsight, game.id) or GameInsight(game_id=game.id)
                insight.catalog_uid = selected.uid
                insight.asset_kind = selected.kind
                db.add(insight)
            results.append(
                {"game_id": game.id, "status": report["status"], "problems": len(report["problems"])}
            )
        return {
            "items": results,
            "complete": sum(r["status"] == "complete" for r in results),
            "total": len(results),
        }

    def filtered(self, body):
        query = active_entries()
        if body.q:
            tokens = re.findall(r"[^\W_]+", body.q, re.UNICODE)[:12]
            if tokens:
                match = " AND ".join('"' + t.replace('"', "") + '"*' for t in tokens)
                query = query.where(
                    CatalogEntry.id.in_(
                        select(text("rowid"))
                        .select_from(text("catalog_fts"))
                        .where(text("catalog_fts MATCH :match"))
                        .params(match=match)
                    )
                )
        for field in ["source_id", "platform", "system", "genre", "kind"]:
            value = getattr(body, field)
            if value:
                query = query.where(getattr(CatalogEntry, field) == value)
        if body.parents_only:
            query = query.where(CatalogEntry.parent == "")
        if body.collection == "arcade":
            query = query.where(CatalogEntry.platform.in_(ARCADE_PLATFORMS))
        if body.collection == "neogeo":
            query = query.where(CatalogEntry.platform == "neogeo")
        if body.collection == "multiplayer":
            query = query.where(CatalogEntry.players >= 2)
        if body.collection == "preferred":
            query = query.where(CatalogEntry.uid.in_(select(CatalogPreference.preferred_uid)))
        if body.collection in {"favorites", "tested", "missing", "unsynced", "owned"}:
            owned = select(GameInsight.catalog_uid).join(Game, Game.id == GameInsight.game_id)
            if body.collection == "favorites":
                owned = owned.where(Game.favorite.is_(True))
            if body.collection == "tested":
                owned = owned.where(
                    GameInsight.test_status == "passed",
                    GameInsight.test_evidence["sha256"].as_string() == Game.sha256,
                )
            if body.collection == "missing":
                owned = owned.join(ArcadeValidation, ArcadeValidation.game_id == Game.id).where(
                    ArcadeValidation.status == "incomplete"
                )
            if body.collection == "unsynced":
                owned = owned.where(
                    ~exists(
                        select(SyncPresence.id).where(
                            SyncPresence.game_id == Game.id, SyncPresence.sha256 == Game.sha256
                        )
                    )
                )
            query = query.where(CatalogEntry.uid.in_(owned))
        return query

    def summary(self):
        with self.sessions() as db:
            entries = active_entries().subquery()
            families = (
                select(entries.c.source_id, entries.c.family)
                .where(entries.c.kind == "game")
                .distinct()
                .subquery()
            )
            sources = {s.id: record(s) for s in db.scalars(select(CatalogSource))}
            local_paths = {
                f["path"] for g in db.scalars(select(Game)) for f in (g.files or [{"path": g.local_path}])
            }
            present_files = sum(Path(p).is_file() for p in local_paths)
            return {
                "catalog_records": db.scalar(select(func.count()).select_from(entries)),
                "catalog_games": db.scalar(
                    select(func.count()).select_from(entries).where(entries.c.kind == "game")
                ),
                "unique_families": db.scalar(select(func.count()).select_from(families)),
                "family_scope": "Famiglie parent/clone per catalogo; le fonti diverse non vengono fuse per somiglianza del titolo",
                "clones": db.scalar(select(func.count()).select_from(entries).where(entries.c.parent != "")),
                "bios_records": db.scalar(
                    select(func.count()).select_from(entries).where(entries.c.kind == "bios")
                ),
                "local_files": db.scalar(select(func.count(Game.id))),
                "present_files": present_files,
                "missing_files": len(local_paths) - present_files,
                "discovery_records": db.scalar(select(func.count(DiscoveryEntry.id))),
                "authorized_downloads": db.scalar(
                    select(func.count(DiscoveryEntry.id)).where(
                        DiscoveryEntry.available.is_(True), DiscoveryEntry.downloadable.is_(True)
                    )
                ),
                "validated_games": db.scalar(
                    select(func.count(ArcadeValidation.game_id))
                    .join(Game, Game.id == ArcadeValidation.game_id)
                    .join(GameInsight, GameInsight.game_id == Game.id)
                    .join(CatalogEntry, CatalogEntry.uid == ArcadeValidation.catalog_uid)
                    .join(CatalogSource, CatalogSource.active_run == CatalogEntry.run_id)
                    .where(
                        ArcadeValidation.status == "complete",
                        ArcadeValidation.archive_sha == Game.sha256,
                        ArcadeValidation.source_sha == CatalogSource.sha256,
                        GameInsight.asset_kind == "game",
                    )
                ),
                "tested_games": db.scalar(
                    select(func.count(GameInsight.game_id))
                    .join(Game, Game.id == GameInsight.game_id)
                    .where(
                        GameInsight.test_status == "passed",
                        GameInsight.test_evidence["sha256"].as_string() == Game.sha256,
                    )
                ),
                "tested_scope": "Esiti registrati dall’operatore con dispositivo e prova, distinti dalla validazione degli archivi",
                "platforms": [
                    {
                        "id": key,
                        "name": label,
                        "catalog": db.scalar(
                            select(func.count()).select_from(entries).where(entries.c.platform == key)
                        ),
                        "local": db.scalar(select(func.count(Game.id)).where(Game.platform == key)),
                    }
                    for key, label in PLATFORMS.items()
                ],
                "sources": list(sources.values()),
            }

    def audit_device(self, device_id, run_id):
        config = self.devices.get_device(device_id)
        with self.devices.connect(config) as connection:
            result = self.audit(connection, config, PLATFORMS)
        result["checked_at"] = now().isoformat()
        with self.sessions.begin() as db:
            device = db.get(Device, device_id)
            device.diagnostics = {**device.diagnostics, "arcade": result}
        return result

    def enrich_catalog(self, body, run_id):
        matches = []
        unresolved = []
        with self.sessions() as db:
            source = self.source(db, body.source_id)
            games = list(db.scalars(select(Game).where(Game.id.in_(body.game_ids))))
        for index, game in enumerate(games):
            self.checkpoint(run_id, {"done": index, "total": len(games)})
            with self.sessions() as db:
                validation = db.get(ArcadeValidation, game.id)
                if (
                    not validation
                    or validation.status != "complete"
                    or validation.archive_sha != game.sha256
                    or validation.source_sha != source.sha256
                    or digest(Path(game.local_path)) != game.sha256
                ):
                    unresolved.append(
                        {
                            "game_id": game.id,
                            "reason": "Associazione richiede validazione DAT attuale e univoca",
                        }
                    )
                    continue
                entry = db.scalar(
                    active_entries().where(
                        CatalogEntry.uid == validation.catalog_uid, CatalogEntry.source_id == source.id
                    )
                )
                if not entry:
                    unresolved.append({"game_id": game.id, "reason": "Record DAT non disponibile"})
                    continue
                values = {
                    "publisher": entry.manufacturer,
                    "genre": entry.genre,
                    "description": entry.details.get("description", ""),
                }
                if entry.year.isdigit() and 1970 <= int(entry.year) <= 2100:
                    values["year"] = int(entry.year)
                if game.title == Path(game.local_path).stem:
                    values["title"] = entry.title
                changes = {k: v for k, v in values.items() if v and (not getattr(game, k) or k == "title")}
            if body.apply:
                with self.lock, self.sessions.begin() as db:
                    current = db.get(Game, game.id)
                    for key, value in changes.items():
                        if getattr(current, key) == getattr(game, key):
                            setattr(current, key, value)
            matches.append({"game_id": game.id, "title": game.title, "changes": changes})
        return {"matches": matches, "unresolved": unresolved, "applied": body.apply}

    def prepare_games(self, games, config=None, connection=None):
        reports = []
        audit = None
        new_platforms = {"sg-1000", "pcengine", "atari2600", "atari7800", "gamegear", "ngp", "ngpc"}
        if connection and any(g.platform in ARCADE_PLATFORMS | new_platforms for g in games):
            audit = self.audit(connection, config, PLATFORMS)
        for game in games:
            if game.platform not in ARCADE_PLATFORMS:
                if audit and game.platform in new_platforms:
                    launch = game.files[0]["relative"]
                    default, _ = configured_core(
                        audit,
                        game.platform,
                        Path(launch).stem,
                        rom_path=f"{config['rom_root']}/{game.platform}/rlm-{game.sha256[:24]}/{launch}",
                    )
                    if not default or default not in audit["installed_cores"]:
                        raise ValueError(game.title + ": core configurato non rilevato sul Raspberry")
                continue
            with self.sessions() as db:
                validation = db.get(ArcadeValidation, game.id)
                insight = db.get(GameInsight, game.id)
                if not validation or validation.status != "complete" or validation.archive_sha != game.sha256:
                    raise ValueError(
                        game.title
                        + ": validare prima il ROM set con un DAT compatibile; archivi incompleti non esportabili"
                    )
                entry = db.scalar(active_entries().where(CatalogEntry.uid == validation.catalog_uid))
                if not entry:
                    raise ValueError("Associazione DAT non più disponibile")
                source = self.source(db, entry.source_id)
                if source.sha256 != validation.source_sha:
                    raise ValueError("DAT aggiornato: ripetere la validazione")
                report = validation.report
                if not report["launchable"]:
                    raise ValueError(report["launch_note"] or "BIOS/dispositivo non esportabile come gioco")
                target = "neogeo" if entry.platform == "neogeo" else game.platform
                core = insight.preferred_core or source.config.get("core")
                if config:
                    preferred = db.get(Setting, "core:" + config["device_id"] + ":" + target)
                    if preferred and not insight.preferred_core:
                        core = preferred.value
                if not core:
                    raise ValueError("Scegliere un profilo core per il DAT")
                files = []
                for name, archive in report["archives"].items():
                    path = local_path(archive["path"])
                    if path.stat().st_size != archive["size"] or digest(path) != archive["sha256"]:
                        raise ValueError("Dipendenza arcade modificata: " + name)
                    if name in report["bios"] and name != report["main_archive"]:
                        continue
                    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,150}", name) or name in {".", ".."}:
                        raise ValueError("Nome tecnico non esportabile in sicurezza")
                    if path.suffix.lower() not in PROFILES.get(core, {}).get("extensions", []):
                        raise ValueError("Formato archivio non supportato dal core scelto")
                    files.append({**archive, "relative": name + path.suffix.lower()})
                files.sort(key=lambda f: Path(f["relative"]).stem != report["main_archive"])
                if not files or Path(files[0]["relative"]).stem != report["main_archive"]:
                    raise ValueError("Archivio di avvio mancante")
                item = {
                    "game_id": game.id,
                    "set_name": entry.name,
                    "core": core,
                    "source_id": source.id,
                    "source_sha": source.sha256,
                    "source_version": source.config.get("version"),
                    "bios": report["bios"],
                    "mode": validation.mode,
                    "completeness": "complete",
                    "compatibility": "not_assessed",
                    "tested": insight.test_status,
                }
                if audit:
                    observed = audit["cores"].get(core, {})
                    binding = db.get(CoreBinding, fingerprint([config["device_id"], source.id, core]))
                    ok, reason = compatible(source, core, observed, binding)
                    if not ok:
                        raise ValueError(game.title + ": " + reason)
                    default, available = configured_core(
                        audit,
                        target,
                        entry.name,
                        config["rom_root"],
                        Path(game.local_path).suffix.lower(),
                        f"{config['rom_root']}/{target}/rlm-{game.sha256[:24]}/{files[0]['relative']}",
                    )
                    if core not in available:
                        raise ValueError("Core non configurato per " + target)
                    if default != core:
                        raise ValueError(
                            "Il core preferito non coincide con il default remoto: configurarlo nella sessione locale RetroPie, quindi ripetere il dry-run"
                        )
                    item.update(
                        compatibility="dat_core_matched",
                        compatibility_basis=reason,
                        core_sha256=observed["sha256"],
                        core_version=observed["version"],
                    )
                    # BIOS archives are never added to the transfer list. Verify actual content remotely.
                    external_bios = [
                        name
                        for name in report["bios"]
                        if name in report["archives"] and name != report["main_archive"]
                    ]
                    if external_bios:
                        if core != "lr-fbneo":
                            raise ValueError(
                                "BIOS esterno MAME: usare un set full-non-merged ottenuto legittimamente; nessuna copia BIOS automatica"
                            )
                        expected = {
                            name: [
                                c["expected"]
                                for c in report["checks"]
                                if c["role"] == "bios" and c["set"] == name
                            ]
                            for name in external_bios
                        }
                        check = rpc(
                            connection, BIOS_CHECK, {"root": config["bios_root"], "expected": expected}
                        )
                        if not check["complete"]:
                            raise ValueError(
                                "BIOS remoto mancante o non corrispondente al DAT: "
                                + ", ".join(check["missing"])
                            )
                        item["bios_verified"] = check
                game._arcade_files = files
                game._export_platform = target
                game._arcade_report = item
                reports.append(item)
        return reports

    def routes(self):
        router = APIRouter(prefix="/api/intelligence")

        @router.get("/summary")
        def summary():
            return self.summary()

        @router.get("/sources")
        def sources():
            with self.sessions() as db:
                return [
                    {**record(s), "count": self.source_count(s.active_run)}
                    for s in db.scalars(select(CatalogSource))
                ]

        @router.post("/imports", status_code=202)
        def start_import(body: CatalogImport):
            allowed(body.path, self.roots())
            return self.queue(
                "catalog_import", lambda run_id: self.import_catalog(body, run_id), body.source_id
            )

        @router.post("/official-catalogs", status_code=202)
        def official(body: OfficialCatalog):
            return self.queue(
                "catalog_import", lambda r: fetch_catalog(self, body, r), "official-" + body.provider
            )

        @router.get("/runs")
        def runs():
            with self.sessions() as db:
                return [
                    record(r)
                    for r in db.scalars(select(CatalogRun).order_by(CatalogRun.created_at.desc()).limit(30))
                ]

        @router.get("/runs/{run_id}")
        def run_detail(run_id: str):
            with self.sessions() as db:
                run = db.get(CatalogRun, run_id)
                if not run:
                    raise HTTPException(404, "Operazione non trovata")
                return record(run)

        @router.post("/runs/{run_id}/cancel")
        def cancel(run_id: str):
            with self.sessions.begin() as db:
                run = db.get(CatalogRun, run_id)
                if not run or run.status not in ACTIVE:
                    raise ValueError("Operazione non annullabile")
                run.status = "cancelling"
            return {"ok": True}

        @router.post("/search")
        def search(
            body: CatalogFilters, page: int = Query(1, ge=1), page_size: int = Query(36, ge=1, le=100)
        ):
            query = self.filtered(body)
            with self.sessions() as db:
                total = db.scalar(select(func.count()).select_from(query.subquery()))
                items = list(
                    db.scalars(
                        query.order_by(CatalogEntry.title, CatalogEntry.id)
                        .offset((page - 1) * page_size)
                        .limit(page_size)
                    )
                )
                owned: dict[str, list[int]] = {}
                for insight in db.scalars(
                    select(GameInsight).where(GameInsight.catalog_uid.in_([e.uid for e in items]))
                ):
                    owned.setdefault(insight.catalog_uid, []).append(insight.game_id)
                return {
                    "total": total,
                    "page": page,
                    "items": [
                        {
                            **{k: v for k, v in record(e).items() if k not in {"components", "details"}},
                            "owned_game_ids": owned.get(e.uid, []),
                        }
                        for e in items
                    ],
                }

        @router.get("/entries/{uid}")
        def entry_detail(uid: str):
            with self.sessions() as db:
                entry = db.scalar(active_entries().where(CatalogEntry.uid == uid))
                if not entry:
                    raise HTTPException(404, "Voce catalogo non trovata")
                source = self.source(db, entry.source_id)
                variants = list(
                    db.scalars(
                        active_entries()
                        .where(CatalogEntry.source_id == entry.source_id, CatalogEntry.family == entry.family)
                        .limit(500)
                    )
                )
                preference = db.get(CatalogPreference, entry.source_id + ":" + fingerprint(entry.family))
                return {
                    **record(entry),
                    "source": record(source),
                    "variants": [{"uid": v.uid, "name": v.name, "title": v.title} for v in variants],
                    "preferred_uid": preference.preferred_uid if preference else None,
                    "download_authorized": False,
                }

        @router.post("/preferred")
        def preferred(body: PreferredInput):
            with self.sessions.begin() as db:
                entry = db.scalar(active_entries().where(CatalogEntry.uid == body.uid))
                if not entry:
                    raise ValueError("Record non trovato")
                db.merge(
                    CatalogPreference(
                        family_key=entry.source_id + ":" + fingerprint(entry.family), preferred_uid=entry.uid
                    )
                )
            return {"ok": True}

        @router.post("/validate", status_code=202)
        def validate(body: ValidateInput):
            return self.queue("arcade_validation", lambda r: self.validate(body, r), body.source_id)

        @router.get("/games/{game_id}")
        def game_insight(game_id: int):
            with self.sessions() as db:
                game = db.get(Game, game_id)
                if not game:
                    raise HTTPException(404, "Gioco non trovato")
                insight = db.get(GameInsight, game_id)
                return {
                    "game": record(game),
                    "insight": record(insight) if insight else None,
                    "validation": self.validation_view(db, game),
                    "sync": [
                        record(s)
                        for s in db.scalars(select(SyncPresence).where(SyncPresence.game_id == game_id))
                    ],
                }

        @router.put("/games/{game_id}")
        def save_insight(game_id: int, body: InsightInput):
            if body.test_status != "untested" and (not body.device_id or len(body.evidence) < 12):
                raise ValueError("Indicare dispositivo e prova del test effettivo")
            if body.screenshot_path:
                path = allowed(body.screenshot_path, self.roots())
                if (
                    not body.media_rights_confirmed
                    or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}
                    or path.stat().st_size > 20_000_000
                ):
                    raise ValueError("Screenshot locale autorizzato PNG/JPG/WebP, massimo 20 MB")
            with self.lock, self.sessions.begin() as db:
                game = db.get(Game, game_id)
                if not game:
                    raise HTTPException(404, "Gioco non trovato")
                if body.device_id and not db.get(Device, body.device_id):
                    raise ValueError("Dispositivo non trovato")
                value = db.get(GameInsight, game_id) or GameInsight(game_id=game_id)
                value.preferred_core = body.preferred_core
                value.machine_mode = body.machine_mode
                value.test_status = body.test_status
                value.screenshot_path = body.screenshot_path
                value.test_evidence = (
                    {
                        "device_id": body.device_id,
                        "note": body.evidence,
                        "recorded_at": now().isoformat(),
                        "basis": "operator_report",
                        "sha256": game.sha256,
                    }
                    if body.test_status != "untested"
                    else {}
                )
                db.add(value)
            return {"ok": True}

        @router.get("/games/{game_id}/screenshot")
        def screenshot(game_id: int):
            with self.sessions() as db:
                value = db.get(GameInsight, game_id)
                if not value or not value.screenshot_path:
                    raise HTTPException(404, "Screenshot assente")
                return FileResponse(allowed(value.screenshot_path, self.roots()))

        @router.get("/owned")
        def owned(
            q: str = "",
            platform: str = "",
            collection: str = "",
            genre: str = "",
            page: int = Query(1, ge=1),
            page_size: int = Query(36, ge=1, le=100),
        ):
            query = (
                select(Game)
                .outerjoin(GameInsight, Game.id == GameInsight.game_id)
                .outerjoin(ArcadeValidation, Game.id == ArcadeValidation.game_id)
            )
            if q:
                query = query.where(Game.title.icontains(q, autoescape=True))
            if platform:
                query = query.where(Game.platform == platform)
            if genre:
                query = query.where(Game.genre == genre)
            if collection == "arcade":
                query = query.where(Game.platform.in_(ARCADE_PLATFORMS))
            if collection == "neogeo":
                query = query.where(Game.platform == "neogeo")
            if collection == "favorites":
                query = query.where(Game.favorite.is_(True))
            if collection == "tested":
                query = query.where(
                    GameInsight.test_status == "passed",
                    GameInsight.test_evidence["sha256"].as_string() == Game.sha256,
                )
            if collection == "missing":
                query = query.where(ArcadeValidation.status == "incomplete")
            if collection == "unsynced":
                query = query.where(
                    ~exists(
                        select(SyncPresence.id).where(
                            SyncPresence.game_id == Game.id, SyncPresence.sha256 == Game.sha256
                        )
                    )
                )
            if collection == "multiplayer":
                query = query.where(
                    GameInsight.catalog_uid.in_(
                        active_entries().with_only_columns(CatalogEntry.uid).where(CatalogEntry.players >= 2)
                    )
                )
            with self.sessions() as db:
                total = db.scalar(select(func.count()).select_from(query.subquery()))
                games = list(
                    db.scalars(
                        query.order_by(Game.title, Game.id).offset((page - 1) * page_size).limit(page_size)
                    )
                )
                items = []
                for game in games:
                    insight = db.get(GameInsight, game.id)
                    validation = db.get(ArcadeValidation, game.id)
                    items.append(
                        {
                            **record(game),
                            "insight": record(insight) if insight else None,
                            "validation_status": self.validation_view(db, game)["status"]
                            if validation
                            else "unvalidated",
                        }
                    )
                return {"items": items, "total": total}

        @router.post("/metadata", status_code=202)
        def metadata(body: CatalogMatch):
            return self.queue("catalog_matching", lambda r: self.enrich_catalog(body, r), body.source_id)

        @router.post("/devices/{device_id}/audit", status_code=202)
        def audit(device_id: str):
            return self.queue("core_audit", lambda r: self.audit_device(device_id, r))

        @router.get("/profiles")
        def profiles():
            with self.sessions() as db:
                return {
                    "profiles": PROFILES,
                    "bindings": [record(b) for b in db.scalars(select(CoreBinding))],
                }

        @router.post("/bindings")
        def bind(body: BindCore):
            with self.sessions.begin() as db:
                source = self.source(db, body.source_id)
                device = db.get(Device, body.device_id)
                observed = (
                    (device.diagnostics if device else {})
                    .get("arcade", {})
                    .get("cores", {})
                    .get(body.core, {})
                )
                if not observed.get("installed") or not observed.get("version") or not observed.get("sha256"):
                    raise ValueError("Rilevare prima versione e hash del core sul dispositivo")
                if source.config.get("core") != body.core:
                    raise ValueError("Il DAT appartiene a un altro core")
                db.merge(
                    CoreBinding(
                        id=fingerprint([body.device_id, body.source_id, body.core]),
                        device_id=body.device_id,
                        source_id=body.source_id,
                        core=body.core,
                        source_sha=source.sha256,
                        binary_sha=observed["sha256"],
                        version=observed["version"],
                        evidence=body.evidence,
                    )
                )
            return {"ok": True}

        @router.post("/core-preferences")
        def preference(body: CorePreference):
            if body.platform not in ARCADE_PLATFORMS:
                raise ValueError("Profilo previsto per sistemi arcade")
            with self.sessions.begin() as db:
                device = db.get(Device, body.device_id)
                if not device or not device.diagnostics.get("arcade", {}).get("cores", {}).get(
                    body.core, {}
                ).get("installed"):
                    raise ValueError("Core non rilevato")
                db.merge(Setting(key="core:" + body.device_id + ":" + body.platform, value=body.core))
            return {
                "ok": True,
                "remote_configuration_changed": False,
                "message": "Preferenza locale salvata; il dry-run verifica anche il core configurato sul Raspberry",
            }

        return router


BIOS_CHECK = r"""
import json,base64,sys,pathlib,zipfile,hashlib,zlib,stat
args=json.loads(base64.b64decode(sys.argv[1])); root=pathlib.Path(args['root']); missing=[]; verified=[]
for name,expected in args['expected'].items():
 good=False
 for path in [root/(name+'.zip'),root/'fbneo'/(name+'.zip')]:
  if not path.is_file() or any(p.is_symlink() for p in [path]+list(path.parents)):continue
  if path.stat().st_size>64000000:continue
  with zipfile.ZipFile(path) as archive:
   entries=archive.infolist()
   if len(entries)>2000 or sum(e.file_size for e in entries)>128000000:continue
   if len({e.filename.casefold() for e in entries})!=len(entries):continue
   if any(e.filename.startswith(('/', '\\')) or '..' in pathlib.PurePosixPath(e.filename.replace('\\','/')).parts or ':' in e.filename for e in entries):continue
   if any(stat.S_ISLNK(e.external_attr>>16) or e.flag_bits&1 for e in entries):continue
   found={}
   for item in expected:
    try:
     h1=hashlib.sha1();h2=hashlib.sha256();md=hashlib.md5();crc=0;size=0
     with archive.open(item['name']) as stream:
      for block in iter(lambda:stream.read(65536),b''):
       size+=len(block)
       if size>128000000:raise ValueError('BIOS troppo grande')
       h1.update(block);h2.update(block);md.update(block);crc=zlib.crc32(block,crc)
     value={'sha1':h1.hexdigest(),'sha256':h2.hexdigest(),'md5':md.hexdigest(),'crc':'%08x'%(crc&0xffffffff)}
     found[item['name']]=size==item['size'] and all(value[k]==item[k] for k in value if item.get(k))
    except KeyError:found[item['name']]=False
   if expected and all(found.values()):good=True;verified.append(str(path));break
 if not good:missing.append(name)
print(json.dumps({'complete':not missing,'missing':missing,'verified_paths':verified,'copied':False}))
"""
