"""Durable, per-item orchestration over the existing import, media and SFTP services."""

import logging
import threading
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import paramiko
from fastapi import HTTPException
from sqlalchemy import select

from backend.acquisition import record
from backend.acquisition_schemas import EnrichInput
from backend.archive_import import ARCHIVES
from backend.archive_pipeline import ArchiveAnalyzer, review
from backend.collection_schemas import MediaApplyInput, MediaPreviewInput
from backend.db import (
    ArcadeValidation,
    CatalogRun,
    CatalogSource,
    Device,
    Game,
    GameInsight,
    InstallationBatch,
    InstallationItem,
    InstallationUpload,
    Setting,
    SyncRun,
    now,
)
from backend.devices import BUSY
from backend.identification import Identifier, enumerate_files
from backend.import_service import import_candidate
from backend.installation_preflight import preflight
from backend.paths import allowed
from backend.sync_schemas import SyncConfirm, SyncControl, SyncInput

logger = logging.getLogger("rlm")
ACTIVE = {
    "reanalyzing",
    "queued",
    "ready",
    "validating",
    "importing",
    "enriching",
    "preparing_sync",
    "transferring",
    "verifying",
    "waiting_device",
    "pending_refresh",
}
STATES = ACTIVE | {
    "prepared",
    "awaiting_decision",
    "ignored",
    "failed",
    "cancelled",
    "paused",
    "installed",
    "imported_local",
}


class Hold(Exception):
    pass


def failure(phase, file, exc):
    reason = str(exc.detail if isinstance(exc, HTTPException) else exc)
    remedy = "Correggere la causa indicata e scegliere Riprova; se i file sono cambiati, avviare una nuova analisi."
    if any(word in reason.lower() for word in ("bios", "dat", "core")):
        remedy = "Controllare la diagnostica e i componenti ottenuti legittimamente. Non vengono scaricati BIOS o modificati i core."
    if "spazio" in reason.lower():
        remedy = "Liberare spazio autonomamente o scegliere un altro dispositivo; la riserva di sicurezza resta applicata."
    if any(word in reason.lower() for word in ("remoto", "gamelist", "conflitto")):
        remedy = "Controllare il conflitto e riprovare per rigenerare il dry-run; nessun file esistente viene sovrascritto senza verifica."
    return {
        "phase": phase,
        "file": file,
        "cause": reason,
        "operation": phase,
        "remedy": remedy,
        "retryable": True,
    }


class Installations:
    def __init__(self, sessions, data_dir, lock, devices, acquisition, intelligence, collections, media):
        self.sessions, self.data, self.lock = sessions, data_dir, lock
        self.devices, self.acquisition, self.intelligence = devices, acquisition, intelligence
        self.collections, self.media = collections, media
        self.identifier = Identifier(sessions)
        self.archives = ArchiveAnalyzer(self.identifier, data_dir)
        self.preflight = preflight
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.worker = None
        self.offline_until = {}
        self.es_cache = {}
        self.router = None

    def roots(self, batch):
        with self.sessions() as db:
            setting = db.get(Setting, "library")
            roots = list(setting.value.get("import_roots", [])) if setting else []
        roots.append(str(self.data / "downloads"))
        roots.append(str(self.archives.store.root))
        if batch.request.get("upload"):
            roots.append(str(self.data / "inbox" / batch.id))
        return roots

    def start(self):
        self.es_cache.clear()
        self.archives.store.recover()
        # A committed candidate/import/sync ID is a checkpoint. Never recreate library rows.
        with self.sessions.begin() as db:
            for batch in db.scalars(select(InstallationBatch).where(InstallationBatch.status == "scanning")):
                batch.status = "queued"
            for item in db.scalars(select(InstallationItem).where(InstallationItem.status.in_(ACTIVE))):
                item.next_retry = 0
        self.worker = threading.Thread(target=self.loop, name="installation-orchestrator", daemon=True)
        self.worker.start()

    def shutdown(self):
        self.stop.set()
        self.wake.set()
        if self.worker:
            self.worker.join()

    def loop(self):
        while not self.stop.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("Installation scheduler")
            self.wake.wait(0.5)
            self.wake.clear()

    def checkpoint(self, batch_id):
        if self.stop.is_set():
            raise Hold()
        with self.sessions() as db:
            batch = db.get(InstallationBatch, batch_id)
            if not batch or batch.control != "run":
                raise Hold()

    def update(self, item_id, status=None, **changes):
        if status is not None and status not in STATES:
            raise ValueError("Stato installazione non valido")
        with self.sessions.begin() as db:
            item = db.get(InstallationItem, item_id)
            batch = db.get(InstallationBatch, item.batch_id)
            if status in ACTIVE and batch.control != "run":
                status = "paused" if batch.control == "pause" else "cancelled"
            if status:
                item.status = status
                item.phase = status
            for key, value in changes.items():
                setattr(item, key, value)
            item.updated_at = now()

    def create(self, body, upload=False):
        payload = body.model_dump()
        with self.lock, self.sessions.begin() as db:
            old = db.scalar(
                select(InstallationBatch).where(InstallationBatch.request_key == body.request_key)
            )
            if old:
                if old.request.get("input") != payload:
                    raise ValueError("Chiave richiesta già usata per una selezione differente")
                return record(old)
            device_id = body.device_id
            if body.mode == "install":
                device = (
                    db.get(Device, device_id)
                    if device_id
                    else db.scalar(select(Device).order_by(Device.is_default.desc(), Device.id))
                )
                if not device:
                    raise ValueError(
                        "Configurare un Raspberry in Dispositivi oppure scegliere l'importazione locale"
                    )
                device_id = device.id
            batch = InstallationBatch(
                id=str(uuid4()),
                request_key=body.request_key,
                device_id=device_id,
                mode=body.mode,
                status="draft" if upload else "queued",
                request={"input": payload, "upload": upload, "options": {}},
            )
            if not upload:
                for path in body.paths:
                    allowed(path, self.roots(batch))
            db.add(batch)
            db.flush()
            result = record(batch)
        self.wake.set()
        return result

    def analysis_rows(self, path, root, roots, paths, checkpoint):
        if path.suffix.lower() in {".rar", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".cab", ".ecm", ".ape"}:
            return [
                (
                    path,
                    review(
                        path,
                        "Formato " + path.suffix.upper() + " non supportato per l'installazione. "
                        "Sono supportati ZIP/7z con ROM o immagini complete e descrittori originali. "
                        "Nessuna estrazione o conversione manuale richiesta dall'app.",
                    ),
                )
            ]
        if path.suffix.lower() in ARCHIVES:
            return self.archives.analyze(path, root, roots, checkpoint)
        return [(path, self.identifier.identify(path, root, roots, paths, checkpoint))]

    def save_rows(self, batch_id, rows, replace_id=None):
        # One transaction publishes the container and all children, including after a crash/retry.
        with self.lock, self.sessions.begin() as db:
            for index, (path, result) in enumerate(rows):
                current = (
                    db.get(InstallationItem, replace_id)
                    if index == 0 and replace_id
                    else db.scalar(
                        select(InstallationItem).where(
                            InstallationItem.batch_id == batch_id, InstallationItem.source_key == str(path)
                        )
                    )
                )
                if current and (
                    current.game_id
                    or current.status not in {"reanalyzing", "failed", "awaiting_decision", "ignored"}
                ):
                    continue
                if current is None:
                    current = InstallationItem(id=str(uuid4()), batch_id=batch_id, source_key=str(path))
                    db.add(current)
                for key, value in result.items():
                    if key != "consumed":
                        setattr(current, key, value)
                current.game_id = result["identification"].get("existing_game_id")
                current.phase, current.error = current.status, {}
                current.updated_at = now()

    def reanalyze(self, item_id):
        with self.lock, self.sessions.begin() as db:
            item = db.get(InstallationItem, item_id)
            if not item or item.status not in {"awaiting_decision", "failed", "ignored"}:
                raise ValueError("Rianalisi disponibile per elementi da verificare, esclusi o falliti")
            if item.game_id or item.sync_run_id:
                raise ValueError("Elemento già importato: usare Riprova per riprendere l'installazione")
            batch = db.get(InstallationBatch, item.batch_id)
            if batch.control != "run":
                raise ValueError("Riprendere prima il batch in pausa/annullato")
            item.status = item.phase = "reanalyzing"
            item.error, item.next_retry = {}, 0
            batch.status = "running" if batch.authorized else "preview"
        self.wake.set()
        return {"id": item_id}

    def scan(self, batch):
        try:
            self.checkpoint(batch.id)
            with self.sessions.begin() as db:
                db.get(InstallationBatch, batch.id).status = "scanning"
            roots = self.roots(batch)
            values = (
                [str(self.data / "inbox" / batch.id)]
                if batch.request.get("upload")
                else batch.request["input"]["paths"]
            )
            paths = enumerate_files(values, roots, batch.request["input"].get("recursive", True))
            consumed: set[Path] = set()
            for index, path in enumerate(paths):
                self.checkpoint(batch.id)
                if path in consumed:
                    continue
                root = next(Path(r).resolve() for r in roots if path.is_relative_to(Path(r).resolve()))
                with self.sessions() as db:
                    existing = db.scalar(
                        select(InstallationItem).where(
                            InstallationItem.batch_id == batch.id, InstallationItem.source_key == str(path)
                        )
                    )
                if existing:
                    consumed.update(Path(f["path"]) for f in existing.candidate.get("files", []))
                    continue
                try:
                    rows = self.analysis_rows(path, root, roots, paths, lambda: self.checkpoint(batch.id))
                    for _, result in rows:
                        consumed.update(result.pop("consumed", []))
                    self.save_rows(batch.id, rows)
                    with self.sessions.begin() as db:
                        db.get(InstallationBatch, batch.id).progress = {
                            "scanned_files": index + 1,
                            "total_files": len(paths),
                        }
                    continue
                except Hold:
                    raise
                except Exception as exc:
                    row = InstallationItem(
                        id=str(uuid4()),
                        batch_id=batch.id,
                        source_key=str(path),
                        status="failed",
                        phase="identifying",
                        identification={"title": path.stem, "reason": str(exc)},
                        error=failure("identifying", str(path), exc),
                    )
                with self.sessions.begin() as db:
                    db.add(row)
                    db.get(InstallationBatch, batch.id).progress = {
                        "scanned_files": index + 1,
                        "total_files": len(paths),
                    }
            with self.sessions.begin() as db:
                db.get(InstallationBatch, batch.id).status = "preview"
        except Hold:
            with self.sessions.begin() as db:
                db.get(InstallationBatch, batch.id).status = "queued"
        except Exception as exc:
            with self.sessions.begin() as db:
                current = db.get(InstallationBatch, batch.id)
                current.status, current.error = "failed", failure("scanning", "", exc)

    def tick(self):
        with self.sessions() as db:
            batches = list(
                db.scalars(
                    select(InstallationBatch)
                    .where(
                        InstallationBatch.control == "run",
                        InstallationBatch.status.in_({"queued", "scanning", "preview", "running", "waiting"}),
                    )
                    .order_by(InstallationBatch.created_at)
                )
            )
        for batch in batches:
            if self.stop.is_set():
                return
            if batch.status == "queued" and not batch.authorized:
                self.scan(batch)
            else:
                with self.sessions() as db:
                    items = list(
                        db.scalars(
                            select(InstallationItem)
                            .where(
                                InstallationItem.batch_id == batch.id,
                                InstallationItem.status.in_(ACTIVE),
                                InstallationItem.next_retry <= time.time(),
                            )
                            .order_by(InstallationItem.created_at)
                        )
                    )
                for item in items:
                    if not batch.authorized and item.status != "reanalyzing":
                        continue
                    try:
                        self.checkpoint(batch.id)
                        self.advance(batch, item)
                    except Hold:
                        break
                    except (OSError, paramiko.SSHException, EOFError) as exc:
                        if item.phase in {"preparing_sync", "pending_refresh", "waiting_device"}:
                            self.offline_until[batch.device_id] = time.time() + 30
                            self.update(
                                item.id,
                                "waiting_device",
                                next_retry=time.time() + 30,
                                error=failure(item.phase, item.source_key, exc),
                            )
                        else:
                            self.update(item.id, "failed", error=failure(item.phase, item.source_key, exc))
                    except Exception as exc:
                        with self.sessions() as db:
                            phase = db.get(InstallationItem, item.id).phase
                        extra = (
                            {"progress": {**item.progress, "preflight": exc.report}}
                            if hasattr(exc, "report")
                            else {}
                        )
                        self.update(item.id, "failed", error=failure(phase, item.source_key, exc), **extra)
                self.summarize(batch.id)

    def summarize(self, batch_id):
        # Serialize count/read/write with retry and reanalysis so a stale summary
        # cannot mark a newly resumed batch terminal.
        with self.lock, self.sessions.begin() as db:
            batch = db.get(InstallationBatch, batch_id)
            counts = Counter(
                db.scalars(select(InstallationItem.status).where(InstallationItem.batch_id == batch_id))
            )
            if batch.authorized:
                batch.status = (
                    "running"
                    if any(counts[s] for s in ACTIVE - {"waiting_device", "pending_refresh"})
                    else "waiting"
                    if any(counts[s] for s in {"waiting_device", "pending_refresh", "awaiting_decision"})
                    else "completed_with_errors"
                    if counts["failed"]
                    else "completed"
                )
                batch.updated_at = now()
            return dict(counts)

    def enrich(self, game_id, run_id):
        warnings: list[str] = []
        try:
            result = self.acquisition.enrich(EnrichInput(game_ids=[game_id], apply=True, covers=False))
            warnings.extend(x["reason"] for x in result["unresolved"])
            plan = self.media.preview(MediaPreviewInput(game_ids=[game_id]), run_id)
            ids = [c["id"] for c in plan["candidates"] if c["recommended"]]
            if ids:
                result = self.media.apply(
                    plan["id"], MediaApplyInput(candidate_ids=ids, confirmed=True), run_id
                )
                warnings.extend(x["error"] for x in result["failed"])
        except Exception as exc:
            warnings.append("Metadati/immagini non disponibili: " + str(exc))
        self.collections.match(run_id, [game_id])
        return {"warnings": warnings}

    def advance(self, batch, item):
        if item.status == "reanalyzing":
            roots = self.roots(batch)
            path = allowed(item.source_key, roots)
            root = next(Path(r).resolve() for r in roots if path.is_relative_to(Path(r).resolve()))
            # Include existing siblings for CUE/M3U grouping; stay within this authorized directory.
            paths = enumerate_files([str(path.parent)], roots, False)
            rows = self.analysis_rows(path, root, roots, paths, lambda: self.checkpoint(batch.id))
            for _, result in rows:
                result.pop("consumed", None)
            self.save_rows(batch.id, rows, replace_id=item.id)
            return
        options = batch.request.get("options", {})
        if item.status in {"ready", "queued", "validating", "importing"}:
            if not item.candidate.get("files"):
                roots = self.roots(batch)
                path = allowed(item.source_key, roots)
                root = next(Path(r).resolve() for r in roots if path.is_relative_to(Path(r).resolve()))
                result = self.identifier.identify(
                    path, root, roots, [path], lambda: self.checkpoint(batch.id)
                )
                result.pop("consumed")
                self.update(item.id, **result)
                return
            if (
                batch.mode == "install"
                and not options.get("keep_local_when_offline", True)
                and not item.game_id
            ):
                config = self.devices.get_device(batch.device_id)
                try:
                    with self.devices.connect(config) as connection:
                        self.preflight(
                            connection, config, item.candidate["platform"], SimpleNamespace(**item.candidate)
                        )
                except (OSError, paramiko.SSHException, EOFError) as exc:
                    self.update(
                        item.id,
                        "waiting_device",
                        next_retry=time.time() + 30,
                        error=failure("preparing_sync", item.source_key, exc),
                    )
                    return
            self.update(item.id, "validating")
            with self.lock, self.sessions.begin() as db:
                game, duplicate = import_candidate(
                    db,
                    item.candidate,
                    self.roots(batch),
                    checkpoint=lambda: self.checkpoint(batch.id),
                    on_verified=lambda: self.update(item.id, "importing"),
                )
                chosen = item.identification.get("chosen")
                if chosen:
                    source = db.get(CatalogSource, chosen["source_id"])
                    if not source or source.sha256 != chosen["source_sha"]:
                        raise ValueError("DAT cambiato: ripetere l'analisi")
                    db.merge(
                        ArcadeValidation(
                            game_id=game.id,
                            catalog_uid=chosen["uid"],
                            source_sha=source.sha256,
                            archive_sha=game.sha256,
                            mode=chosen["mode"],
                            status=chosen["report"]["status"],
                            report=chosen["report"],
                        )
                    )
                    insight = db.get(GameInsight, game.id) or GameInsight(game_id=game.id)
                    insight.catalog_uid = chosen["uid"]
                    db.add(insight)
                current = db.get(InstallationItem, item.id)
                current.game_id, current.status, current.phase = game.id, "enriching", "enriching"
                current.identification = {**current.identification, "duplicate": duplicate}
            return
        if item.status == "enriching":
            if item.enriched or not options.get("enrich", True):
                self.update(
                    item.id, "imported_local" if batch.mode == "local" else "preparing_sync", enriched=True
                )
                return
            run_id = item.progress.get("enrichment_run")
            if not run_id:
                run_id = self.intelligence.queue(
                    "installation_enrich", lambda rid: self.enrich(item.game_id, rid)
                )["id"]
                self.update(item.id, progress={**item.progress, "enrichment_run": run_id})
            else:
                with self.sessions() as db:
                    run = db.get(CatalogRun, run_id)
                if run and run.status in {"completed", "failed", "cancelled"}:
                    warnings = (
                        run.result.get("warnings", [])
                        if run.status == "completed"
                        else ["Arricchimento non completato: " + run.error]
                    )
                    self.update(
                        item.id, enriched=True, warnings=list(dict.fromkeys(item.warnings + warnings))
                    )
            return
        if item.status == "waiting_device":
            if self.offline_until.get(batch.device_id, 0) > time.time():
                return
            self.update(item.id, "preparing_sync" if item.game_id else "ready", error={})
            return
        if item.status == "pending_refresh":
            if self.offline_until.get(batch.device_id, 0) > time.time():
                return
            checked_at, diag = self.es_cache.get(batch.device_id, (0, {}))
            if time.time() - checked_at >= 10:
                diag = self.devices.diagnose(batch.device_id)
                self.es_cache[batch.device_id] = (time.time(), diag)
            if diag["es_running"]:
                self.update(item.id, next_retry=time.time() + 15)
                return
            # Regenerate against ES's final saved metadata, never replay a stale XML plan.
            self.update(item.id, "preparing_sync", sync_run_id="", next_retry=0)
            return
        if item.status in {"preparing_sync", "transferring", "verifying"}:
            if not item.sync_run_id:
                # Only one pipeline plan at a time per device, including previews:
                # prevent several items capturing the same old gamelist before publication.
                with self.sessions() as db:
                    busy = db.scalar(
                        select(SyncRun.id).where(
                            SyncRun.device_id == batch.device_id, SyncRun.status.in_(BUSY)
                        )
                    )
                    preview = db.scalar(
                        select(SyncRun.id)
                        .join(InstallationItem, InstallationItem.sync_run_id == SyncRun.id)
                        .join(InstallationBatch, InstallationBatch.id == InstallationItem.batch_id)
                        .where(
                            SyncRun.device_id == batch.device_id,
                            SyncRun.status == "preview",
                            InstallationItem.id != item.id,
                            InstallationBatch.control == "run",
                            InstallationItem.status.in_(ACTIVE),
                        )
                    )
                if busy or preview:
                    return
                if self.offline_until.get(batch.device_id, 0) > time.time():
                    self.update(item.id, "waiting_device", next_retry=self.offline_until[batch.device_id])
                    return
                config = self.devices.get_device(batch.device_id)
                with self.sessions() as db:
                    game = db.get(Game, item.game_id)
                with self.devices.connect(config) as connection:
                    checked = self.preflight(connection, config, game.platform, game)
                body = SyncInput(
                    device_id=batch.device_id,
                    game_ids=[item.game_id],
                    metadata=True,
                    covers=True,
                    screenshots=True,
                    collection=True,
                    collection_partial=True,
                )
                run_id = self.devices.prepare(body)["id"]
                self.update(
                    item.id,
                    "preparing_sync",
                    sync_run_id=run_id,
                    progress={**item.progress, "preflight": checked},
                )
                return
            with self.sessions() as db:
                run = db.get(SyncRun, item.sync_run_id)
            if not run:
                raise ValueError("Manifest persistente non trovato: riprovare per rigenerarlo")
            progress = {
                **item.progress,
                "sync": run.progress,
                "required_bytes": run.plan.get("required_bytes"),
                "free_bytes": run.plan.get("free_bytes"),
                "destination": run.plan.get("config", {}).get("rom_root"),
            }
            if run.status == "preview":
                if not run.plan.get("can_sync"):
                    raise ValueError("; ".join(run.plan.get("blocked", ["Dry-run bloccato"])))
                try:
                    self.devices.confirm(
                        run.id,
                        SyncConfirm(confirmed=True, rights_confirmed=True, media_rights_confirmed=True),
                    )
                except ValueError as exc:
                    if "impegnato" in str(exc):
                        return
                    raise
                self.update(item.id, "transferring", progress=progress)
            elif run.status in BUSY:
                self.update(
                    item.id,
                    "verifying"
                    if run.progress.get("phase") == "verifying"
                    else "preparing_sync"
                    if run.status == "preparing"
                    else "transferring",
                    progress=progress,
                )
            elif run.status == "completed":
                deferred = run.report.get("metadata_deferred", False)
                history = progress.get("reports", [])
                if not any(r["run_id"] == run.id for r in history):
                    history = (history + [{"run_id": run.id, **run.report}])[-30:]
                progress.update(
                    report=run.report,
                    reports=history,
                    free_bytes=run.report.get("space_after", {}).get("free"),
                )
                self.update(
                    item.id,
                    "pending_refresh" if deferred else "installed",
                    progress=progress,
                    visibility="pending_refresh" if deferred else "awaiting_local_check",
                    error={},
                    next_retry=time.time() + 15 if deferred else 0,
                )
            elif run.status in {"failed", "paused", "cancelled"}:
                transient = any(
                    s in run.error.lower()
                    for s in (
                        "riavvio",
                        "interrotto",
                        "timed out",
                        "timeout",
                        "connection",
                        "unable to connect",
                        "server arrestato",
                        "socket",
                        "winerror",
                    )
                )
                if (
                    run.plan.get("authorization")
                    and (run.status == "paused" or transient)
                    and item.attempts < 3
                ):
                    try:
                        self.devices.control(run.id, SyncControl(action="retry"))
                    except ValueError as exc:
                        if "impegnato" in str(exc):
                            return
                        raise
                    self.update(item.id, "transferring", attempts=item.attempts + 1, progress=progress)
                elif transient and not run.plan.get("authorization"):
                    self.offline_until[batch.device_id] = time.time() + 30
                    self.update(
                        item.id,
                        "waiting_device",
                        sync_run_id="",
                        error=failure("preparing_sync", item.source_key, run.error),
                        next_retry=time.time() + 30,
                    )
                else:
                    raise ValueError(run.error or "Sincronizzazione interrotta: riprovare")

    def confirm(self, batch_id, body):
        with self.lock, self.sessions.begin() as db:
            batch = db.get(InstallationBatch, batch_id)
            if not batch:
                raise HTTPException(404, "Installazione non trovata")
            if batch.authorized:
                return {"id": batch.id}
            if batch.status != "preview":
                raise ValueError("Attendere il completamento dell'analisi")
            batch.authorized, batch.status = True, "running"
            batch.request = {**batch.request, "options": body.model_dump()}
        self.wake.set()
        return {"id": batch_id}

    def retry_item(self, item_id):
        with self.lock, self.sessions.begin() as db:
            item = db.get(InstallationItem, item_id)
            if not item or item.status not in {"failed", "waiting_device", "paused", "cancelled"}:
                raise ValueError("Riprova non disponibile per questo elemento")
            run = db.get(SyncRun, item.sync_run_id) if item.sync_run_id else None
            # Reuse authorized staging after transport failures; conflicts need a fresh preview.
            recover = (
                run
                and run.plan.get("authorization")
                and any(
                    w in run.error.lower()
                    for w in ("interrotto", "timeout", "connection", "socket", "winerror", "riavvio")
                )
            )
            if not recover and (not run or run.status != "paused"):
                item.sync_run_id = ""
            batch = db.get(InstallationBatch, item.batch_id)
            item.status = (
                ("imported_local" if batch.mode == "local" else "preparing_sync")
                if item.game_id and item.enriched
                else "enriching"
                if item.game_id
                else "ready"
            )
            if not item.game_id and not item.candidate.get("files"):
                item.status = "reanalyzing"
            item.phase, item.error, item.attempts, item.next_retry = item.status, {}, 0, 0
            if batch.authorized:
                batch.status = "running"
        self.wake.set()

    def control(self, batch_id, action):
        with self.lock, self.sessions.begin() as db:
            batch = db.get(InstallationBatch, batch_id)
            if not batch:
                raise HTTPException(404, "Installazione non trovata")
            batch.control = "pause" if action == "pause" else "cancel" if action == "cancel" else "run"
            items = list(db.scalars(select(InstallationItem).where(InstallationItem.batch_id == batch_id)))
            jobs = [(i.sync_run_id, i.id) for i in items if i.sync_run_id]
            retry = [i.id for i in items if i.status in {"failed", "waiting_device", "paused", "cancelled"}]
            if action in {"pause", "cancel"}:
                for item in items:
                    if item.status in ACTIVE:
                        item.status = "paused" if action == "pause" else "cancelled"
            if action in {"retry", "resume", "refresh"} and batch.status == "failed" and not batch.authorized:
                batch.status, batch.error = "queued", {}
        if action in {"pause", "cancel"}:
            for run_id, _ in jobs:
                with self.sessions() as db:
                    run = db.get(SyncRun, run_id)
                if run and run.status in BUSY:
                    self.devices.control(run_id, SyncControl(action=action))
        elif action in {"retry", "resume"}:
            for item_id in retry:
                self.retry_item(item_id)
        self.wake.set()
        return {"ok": True}

    def decision(self, item_id, body):
        with self.sessions() as db:
            item = db.get(InstallationItem, item_id)
            if not item or item.status != "awaiting_decision":
                raise ValueError("Elemento non in attesa di decisione")
            batch = db.get(InstallationBatch, item.batch_id)
        if body.action == "skip":
            self.update(item.id, "ignored")
            return {"ok": True}
        if body.variant_source:
            options = item.identification.get("variants", [])
            if body.variant_source not in {o["source"] for o in options}:
                raise ValueError("Variante non presente nell'anteprima")
            with self.lock, self.sessions.begin() as db:
                for option in options:
                    variant = db.scalar(
                        select(InstallationItem).where(
                            InstallationItem.batch_id == batch.id,
                            InstallationItem.source_key == option["source"],
                        )
                    )
                    if (
                        not variant
                        or variant.sync_run_id
                        or variant.status not in {"ignored", "awaiting_decision"}
                    ):
                        raise ValueError("Variante non più selezionabile: rianalizzare")
                    variant.status = "ready" if option["source"] == body.variant_source else "ignored"
                    variant.phase = variant.status
                    variant.identification = {
                        **variant.identification,
                        "variants": [],
                        "reason": "Variante selezionata dall'operatore",
                    }
                if batch.authorized:
                    db.get(InstallationBatch, batch.id).status = "running"
            self.wake.set()
            return {"ok": True}
        roots = self.roots(batch)
        path = allowed(item.source_key, roots)
        root = next(Path(r).resolve() for r in roots if path.is_relative_to(Path(r).resolve()))
        result = self.identifier.identify(path, root, roots, [path], decision=body.model_dump())
        result.pop("consumed")
        self.update(item.id, **result, error={})
        self.wake.set()
        return {"ok": True}

    def detail(self, batch_id, page=1, page_size=100):
        with self.sessions() as db:
            batch = db.get(InstallationBatch, batch_id)
            if not batch:
                raise HTTPException(404, "Installazione non trovata")
            counts = Counter(
                db.scalars(select(InstallationItem.status).where(InstallationItem.batch_id == batch_id))
            )
            items = list(
                db.scalars(
                    select(InstallationItem)
                    .where(InstallationItem.batch_id == batch_id)
                    .order_by(InstallationItem.created_at, InstallationItem.id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            result = []
            for item in items:
                value = record(item)
                game = db.get(Game, item.game_id) if item.game_id else None
                insight = db.get(GameInsight, item.game_id) if item.game_id else None
                value.update(
                    title=game.title
                    if game
                    else item.identification.get("title", Path(item.source_key).stem),
                    platform=game.platform if game else item.identification.get("platform", ""),
                    pc_present=bool(game and all(Path(f["path"]).is_file() for f in game.files)),
                    installed=item.status in {"installed", "pending_refresh"}
                    or bool(item.progress.get("reports")),
                    launched=bool(
                        game
                        and insight
                        and insight.test_status == "passed"
                        and insight.test_evidence.get("sha256") == game.sha256
                        and insight.test_evidence.get("device_id") == batch.device_id
                    ),
                    cover_url=f"/api/games/{game.id}/cover" if game and game.cover_path else "",
                    compatibility="DAT/core verificati"
                    if item.identification.get("chosen") and item.progress.get("reports")
                    else "Avvio non verificato",
                )
                result.append(value)
            uploads = (
                [
                    record(u)
                    for u in db.scalars(
                        select(InstallationUpload).where(InstallationUpload.batch_id == batch_id)
                    )
                ]
                if batch.status == "draft"
                else []
            )
            return {
                **record(batch),
                "counts": dict(counts),
                "items": result,
                "total": sum(counts.values()),
                "uploads": uploads,
            }
