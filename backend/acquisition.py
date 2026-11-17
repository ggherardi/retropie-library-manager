import hashlib
import io
import json
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import func, select

from backend.acquisition_schemas import (
    AcquisitionSettings,
    Confirmation,
    DiscoveryFilters,
    PlanInput,
    TaskAction,
)
from backend.db import DiscoveryEntry, DownloadPlan, DownloadTask, Game, ProviderState, Setting, now
from backend.discovery_sources import LINK_SOURCES, SOURCES, GitHubCatalog, identity, supported_download
from backend.download_manager import ACTIVE, DownloadManager
from backend.network import PublicHTTP
from backend.paths import digest

logger = logging.getLogger("rlm")


def record(model):
    return jsonable_encoder({column.name: getattr(model, column.name) for column in model.__table__.columns})


def fingerprint(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


class Acquisition:
    def __init__(self, sessions, data_dir, lock):
        self.sessions = sessions
        self.data_dir = data_dir
        self.lock = lock
        self.http = PublicHTTP()
        self.manager = DownloadManager(sessions, data_dir, lock, self.http)
        self.manager.cover_loader = lambda snapshot: self.cache_cover(
            DiscoveryEntry(payload=snapshot["payload"])
        )
        self.catalog = GitHubCatalog(self.http, data_dir / "provider_cache")
        self.refresh_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="catalog")
        self.router = self.routes()

    def start(self):
        with self.sessions.begin() as db:
            for key, source in SOURCES.items():
                state = db.get(ProviderState, key)
                if not state:
                    db.add(ProviderState(id=key, name=source["name"]))
                elif state.status == "refreshing":
                    state.status = "error"
                    state.message = "Aggiornamento interrotto. Riprovare."
        self.sync_manifests()
        self.manager.start()

    def shutdown(self):
        self.manager.shutdown()
        self.refresh_pool.shutdown(wait=True)
        self.http.close()

    def settings(self):
        with self.sessions() as db:
            setting = db.get(Setting, "acquisition")
            return AcquisitionSettings(**(setting.value if setting else {}))

    def sync_manifests(self):
        with self.lock, self.sessions.begin() as db:
            source = db.get(Setting, "providers")
            for provider in source.value if source else []:
                provider_id = "manifest-" + provider["id"]
                ids = []
                for entry in provider["entries"]:
                    entry_id = identity(provider_id, entry["id"])
                    ids.append(entry_id)
                    existing = db.get(DiscoveryEntry, entry_id)
                    payload = {
                        "url": entry["url"],
                        "filename": entry["filename"],
                        "expected_sha256": entry["sha256"],
                        "cover": None,
                        "evidence": {
                            "url": entry["rights_url"],
                            "license": entry["license"],
                            "declaration": entry,
                            "basis": "Manifest autorizzato configurato dall'operatore",
                        },
                    }
                    values = dict(
                        id=entry_id,
                        provider_id=provider_id,
                        external_id=entry["id"],
                        title=entry["title"],
                        platform=entry["platform"],
                        source_url=entry["rights_url"],
                        license=entry["license"],
                        size=entry["size"],
                        available=True,
                        downloadable=entry["redistribution_allowed"]
                        and supported_download(entry["platform"], entry["filename"]),
                        sha256=entry["sha256"].lower(),
                        payload=payload,
                        reason=""
                        if supported_download(entry["platform"], entry["filename"])
                        else "Formato di download non supportato",
                    )
                    if existing:
                        for key, value in values.items():
                            setattr(existing, key, value)
                    else:
                        db.add(DiscoveryEntry(**values))
                for missing in db.scalars(
                    select(DiscoveryEntry).where(
                        DiscoveryEntry.provider_id == provider_id, DiscoveryEntry.id.not_in(ids)
                    )
                ):
                    missing.available = False
                    missing.downloadable = False
                    missing.reason = "Rimossa dal manifest"
                db.merge(
                    ProviderState(
                        id=provider_id,
                        name=provider["name"],
                        count=len(ids),
                        status="ready",
                        message="Manifest locale dell'operatore",
                        updated_at=now(),
                    )
                )

    def refresh(self, provider_id):
        if provider_id not in SOURCES:
            raise ValueError("Provider di rete non supportato")
        with self.lock, self.sessions.begin() as db:
            state = db.get(ProviderState, provider_id)
            if state.status == "refreshing":
                return
            state.status = "refreshing"
            state.message = "Lettura inventario pubblico"

        def progress(done, total):
            with self.sessions.begin() as db:
                db.get(ProviderState, provider_id).message = f"Metadati {done} / {total}"

        def update():
            try:
                entries = self.catalog.load(provider_id, progress)
                with self.lock, self.sessions.begin() as db:
                    for old in db.scalars(
                        select(DiscoveryEntry).where(DiscoveryEntry.provider_id == provider_id)
                    ):
                        old.available = False
                        old.downloadable = False
                        old.reason = "Assente dall'ultimo inventario della fonte"
                    for item in entries:
                        old = db.get(DiscoveryEntry, item["id"])
                        if (
                            old
                            and old.payload.get("git_blob_sha1") == item["payload"].get("git_blob_sha1")
                            and old.sha256
                        ):
                            item["sha256"] = old.sha256
                        db.merge(DiscoveryEntry(**item, updated_at=now()))
                    state = db.get(ProviderState, provider_id)
                    state.status = "ready"
                    state.count = len(entries)
                    state.message = (
                        f"{sum(e['downloadable'] for e in entries)} download autorizzati e supportati"
                    )
                    state.updated_at = now()
            except Exception as exc:
                logger.exception("Provider refresh failed")
                with self.sessions.begin() as db:
                    state = db.get(ProviderState, provider_id)
                    state.status = "error"
                    state.message = str(exc)

        self.refresh_pool.submit(update)

    def filtered(self, filters):
        query = select(DiscoveryEntry)
        if filters.q:
            query = query.where(DiscoveryEntry.title.icontains(filters.q, autoescape=True))
        for column, values in [
            (DiscoveryEntry.platform, filters.platforms),
            (DiscoveryEntry.provider_id, filters.sources),
            (DiscoveryEntry.license, filters.licenses),
        ]:
            if values:
                query = query.where(column.in_(values))
        if filters.genre:
            query = query.where(DiscoveryEntry.genre == filters.genre)
        if filters.available_only:
            query = query.where(DiscoveryEntry.available.is_(True), DiscoveryEntry.downloadable.is_(True))
        return query

    def storage(self, selected_bytes=0):
        config = self.settings()
        with self.sessions() as db:
            library = db.scalar(select(func.coalesce(func.sum(Game.size), 0)))
            pending = list(db.scalars(select(DownloadTask).where(DownloadTask.status.in_(ACTIVE))))
        reserved = sum(t.total for t in pending)
        remaining = sum(max(0, t.total - t.received) for t in pending)
        usable = (
            int(config.target_bytes * (100 - config.filesystem_margin_percent) / 100) - config.reserved_bytes
        )
        free = shutil.disk_usage(self.data_dir).free
        fits_target = library + reserved + selected_bytes <= usable
        fits_disk = selected_bytes + remaining + 64 * 1024**2 <= free
        return {
            "library_bytes": library,
            "pending_bytes": reserved,
            "selected_bytes": selected_bytes,
            "target_bytes": config.target_bytes,
            "reserved_bytes": config.reserved_bytes,
            "usable_bytes": usable,
            "estimated_export_bytes": library + reserved + selected_bytes,
            "disk_free_bytes": free,
            "fits_target": fits_target,
            "fits_disk": fits_disk,
            "warnings": ([] if fits_target else ["Capacità RetroPie utile superata"])
            + ([] if fits_disk else ["Spazio locale insufficiente, incluso margine di 64 MiB"]),
        }

    def preview(self, body: PlanInput):
        config = self.settings()
        filters = config.automatic_filters if body.mode == "automatic" else body.filters
        if body.mode == "automatic" and not (filters.platforms and filters.sources and filters.licenses):
            raise ValueError("Configurare piattaforme, fonti e licenze della selezione automatica")
        if body.mode == "manual" and not body.all_filtered and not body.ids:
            raise ValueError("Selezionare almeno un gioco")
        query = self.filtered(filters)
        if body.mode == "manual" and not body.all_filtered:
            query = query.where(DiscoveryEntry.id.in_(body.ids))
        with self.sessions() as db:
            entries = list(db.scalars(query.order_by(DiscoveryEntry.title, DiscoveryEntry.id)))
            known = set(db.scalars(select(Game.sha256)))
            queued = set(db.scalars(select(DownloadTask.entry_id).where(DownloadTask.status.in_(ACTIVE))))
        selected = []
        skipped = {"unsupported": 0, "duplicate": 0, "queued": 0, "budget": 0}
        size = 0
        for entry in entries:
            if not entry.available or not entry.downloadable or not entry.size:
                skipped["unsupported"] += 1
            elif entry.id in queued:
                skipped["queued"] += 1
            elif config.exclude_duplicates and entry.sha256 in known:
                skipped["duplicate"] += 1
            elif body.mode == "automatic" and size + entry.size > config.automatic_max_bytes:
                skipped["budget"] += 1
            else:
                selected.append(
                    {"id": entry.id, "fingerprint": fingerprint(record(entry)), "title": entry.title}
                )
                size += entry.size
                if entry.sha256:
                    known.add(entry.sha256)
        plan_id = str(uuid4())
        result = {
            "id": plan_id,
            "mode": body.mode,
            "count": len(selected),
            "files": len(selected),
            "bytes": size,
            "skipped": skipped,
            "entries": selected,
            "storage": self.storage(size),
            "concurrency": config.concurrency,
            "config_fingerprint": fingerprint(config.model_dump()),
        }
        result["can_confirm"] = bool(selected) and not result["storage"]["warnings"]
        with self.sessions.begin() as db:
            db.add(DownloadPlan(id=plan_id, payload=result))
        return result

    def confirm(self, plan_id):
        with self.lock, self.sessions.begin() as db:
            plan = db.get(DownloadPlan, plan_id)
            if not plan:
                raise ValueError("Riepilogo non trovato")
            if plan.confirmed:
                return {"tasks": plan.tasks}
            config = self.settings()
            if fingerprint(config.model_dump()) != plan.payload["config_fingerprint"]:
                raise ValueError("Impostazioni cambiate. Generare un nuovo riepilogo.")
            if not plan.payload["can_confirm"] or self.storage(plan.payload["bytes"])["warnings"]:
                raise ValueError("Limiti di spazio superati o selezione vuota")
            tasks = []
            for selected in plan.payload["entries"]:
                entry = db.get(DiscoveryEntry, selected["id"])
                if not entry or fingerprint(record(entry)) != selected["fingerprint"]:
                    raise ValueError("Catalogo cambiato. Generare un nuovo riepilogo.")
                if db.scalar(
                    select(DownloadTask.id).where(
                        DownloadTask.entry_id == entry.id, DownloadTask.status.in_(ACTIVE)
                    )
                ):
                    raise ValueError("Un titolo è già in coda. Generare un nuovo riepilogo.")
                task_id = str(uuid4())
                db.add(DownloadTask(id=task_id, entry_id=entry.id, snapshot=record(entry), total=entry.size))
                tasks.append(task_id)
            plan.confirmed = True
            plan.tasks = tasks
        return {"tasks": tasks}

    def cache_cover(self, entry):
        cover = entry.payload.get("cover")
        if not cover:
            raise ValueError("Copertina priva di autorizzazione verificata")
        key = hashlib.sha256(json.dumps(cover, sort_keys=True).encode()).hexdigest()
        folder = self.data_dir / "covers"
        folder.mkdir(exist_ok=True)
        output = folder / f"{key}.png"
        if output.exists():
            return output
        content = self.http.read(cover["url"], 8_000_000)
        if (
            cover.get("git_blob_sha1")
            and hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
            != cover["git_blob_sha1"]
        ):
            raise ValueError("Hash copertina non valido")
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > 20_000_000:
                raise ValueError("Copertina troppo grande")
            image.load()
            temporary = folder / f"{uuid4()}.png"
            image.save(temporary, format="PNG")
            temporary.replace(output)
        return output

    def enrich(self, body):
        with self.sessions() as db:
            games = (
                list(db.scalars(select(Game).where(Game.id.in_(body.game_ids))))
                if body.game_ids
                else list(db.scalars(select(Game)))
            )
            entries = list(db.scalars(select(DiscoveryEntry).where(DiscoveryEntry.available.is_(True))))
        by_sha: dict[str, list[DiscoveryEntry]] = {}
        by_blob: dict[str, list[DiscoveryEntry]] = {}
        for entry in entries:
            if entry.sha256:
                by_sha.setdefault(entry.sha256, []).append(entry)
            if entry.payload.get("git_blob_sha1"):
                by_blob.setdefault(entry.payload["git_blob_sha1"], []).append(entry)
        matches = []
        unresolved = []
        for game in games:
            found = by_sha.get(game.sha256, [])
            if not found and len(game.files) == 1:
                try:
                    path = Path(game.local_path)
                    if digest(path) != game.sha256:
                        raise ValueError("File modificato")
                    blob = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
                    with path.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(65536), b""):
                            blob.update(chunk)
                    found = by_blob.get(blob.hexdigest(), [])
                except (OSError, ValueError):
                    unresolved.append({"game_id": game.id, "reason": "File mancante o modificato"})
                    continue
            if len(found) != 1:
                unresolved.append(
                    {"game_id": game.id, "reason": "Corrispondenza ambigua" if found else "Hash sconosciuto"}
                )
                continue
            entry = found[0]
            changes = {
                key: getattr(entry, key)
                for key in ("author", "year", "genre", "description")
                if not getattr(game, key) and getattr(entry, key)
            }
            if game.license == "Da verificare" and entry.license:
                changes["license"] = entry.license
            if game.provenance == "Importazione locale":
                changes["provenance"] = entry.source_url
            cover_error = None
            if body.apply and body.covers and not game.cover_path and entry.payload.get("cover"):
                try:
                    changes["cover_path"] = str(self.cache_cover(entry))
                except Exception as exc:
                    cover_error = str(exc)
            if body.apply:
                with self.lock, self.sessions.begin() as db:
                    current = db.get(Game, game.id)
                    for key, value in changes.items():
                        # Preserve fields edited manually between preview and application.
                        if getattr(current, key) == getattr(game, key):
                            setattr(current, key, value)
            matches.append(
                {
                    "game_id": game.id,
                    "title": game.title,
                    "entry_id": entry.id,
                    "changes": changes,
                    "cover_available": bool(entry.payload.get("cover")),
                    "cover_error": cover_error,
                }
            )
        return {"applied": body.apply, "matches": matches, "unresolved": unresolved}

    def routes(self):
        router = APIRouter(prefix="/api")

        @router.get("/acquisition/settings")
        def settings():
            return self.settings()

        @router.put("/acquisition/settings")
        def save_settings(body: AcquisitionSettings):
            with self.lock, self.sessions.begin() as db:
                db.merge(Setting(key="acquisition", value=body.model_dump()))
            return body

        @router.get("/acquisition/storage")
        def storage():
            return self.storage()

        @router.get("/discovery/providers")
        def providers():
            with self.sessions() as db:
                return [
                    record(p) for p in db.scalars(select(ProviderState).order_by(ProviderState.id))
                ] + LINK_SOURCES

        @router.post("/discovery/providers/{provider_id}/refresh", status_code=202)
        def refresh(provider_id: str):
            self.refresh(provider_id)
            return {"status": "refreshing"}

        @router.get("/discovery/facets")
        def facets():
            with self.sessions() as db:
                return {
                    key: list(
                        db.scalars(select(column).where(column.is_not(None)).distinct().order_by(column))
                    )
                    for key, column in {
                        "platforms": DiscoveryEntry.platform,
                        "licenses": DiscoveryEntry.license,
                        "genres": DiscoveryEntry.genre,
                    }.items()
                }

        @router.post("/discovery/search")
        def search(
            body: DiscoveryFilters,
            page: int = Query(1, ge=1),
            page_size: int = Query(24, ge=1, le=100),
            sort: str = "title",
        ):
            order = {
                "title": DiscoveryEntry.title.asc(),
                "title_desc": DiscoveryEntry.title.desc(),
                "size": DiscoveryEntry.size.asc(),
                "year": DiscoveryEntry.year.desc(),
            }.get(sort)
            if order is None:
                raise ValueError("Ordinamento non supportato")
            query = self.filtered(body)
            with self.sessions() as db:
                total = db.scalar(select(func.count()).select_from(query.subquery()))
                items = list(
                    db.scalars(
                        query.order_by(order, DiscoveryEntry.id)
                        .offset((page - 1) * page_size)
                        .limit(page_size)
                    )
                )
                imported = set(db.scalars(select(Game.sha256)))
                tasks = {
                    t.entry_id: t for t in db.scalars(select(DownloadTask).order_by(DownloadTask.created_at))
                }
                result = []
                for entry in items:
                    value = record(entry)
                    task = tasks.get(entry.id)
                    value["state"] = (
                        "imported"
                        if entry.sha256 in imported
                        else "downloaded"
                        if task and task.status == "downloaded"
                        else "available"
                        if entry.downloadable and entry.available
                        else "unsupported"
                    )
                    value["queue_status"] = task.status if task else None
                    value["cover_available"] = bool(entry.payload.get("cover"))
                    result.append(value)
                return {"items": result, "total": total}

        @router.get("/discovery/{entry_id}/cover")
        def cover(entry_id: str):
            with self.sessions() as db:
                entry = db.get(DiscoveryEntry, entry_id)
                if not entry:
                    raise HTTPException(404, "Titolo non trovato")
                return FileResponse(self.cache_cover(entry), media_type="image/png")

        @router.post("/acquisition/plans")
        def preview(body: PlanInput):
            return self.preview(body)

        @router.post("/acquisition/plans/{plan_id}/confirm")
        def confirm(plan_id: str, body: Confirmation):
            return self.confirm(plan_id)

        @router.get("/downloads")
        def downloads(page: int = Query(1, ge=1)):
            with self.sessions() as db:
                tasks = list(
                    db.scalars(
                        select(DownloadTask)
                        .order_by(DownloadTask.created_at.desc())
                        .offset((page - 1) * 50)
                        .limit(50)
                    )
                )
                counts = dict(
                    db.execute(select(DownloadTask.status, func.count()).group_by(DownloadTask.status)).all()
                )
                return {"items": [record(t) for t in tasks], "counts": counts, "total": sum(counts.values())}

        @router.post("/downloads/{task_id}/control")
        def control(task_id: str, body: TaskAction):
            if body.action in {"resume", "retry"}:
                with self.sessions() as db:
                    task = db.get(DownloadTask, task_id)
                    if not task:
                        raise HTTPException(404, "Download non trovato")
                    extra = 0 if task.status in ACTIVE else task.total
                if self.storage(extra)["warnings"]:
                    raise ValueError("Limiti di spazio superati. Aggiornare la configurazione.")
            self.manager.control(task_id, body.action)
            return {"ok": True}

        return router
