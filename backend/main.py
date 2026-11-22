import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import RLock
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from backend.acquisition import Acquisition
from backend.acquisition_schemas import EnrichInput
from backend.collections import Collections
from backend.config import DATA, PLATFORMS, PROJECT
from backend.db import Game, Job, Setting, make_engine, sessions
from backend.devices import DeviceService
from backend.exports import LocalTransport
from backend.import_service import import_candidate
from backend.installation_routes import routes as installation_routes
from backend.installations import Installations
from backend.intelligence import Intelligence
from backend.lan_access import Access
from backend.media import MediaService
from backend.paths import allowed, local_path
from backend.providers import ManifestProvider, download
from backend.scanner import ScanCancelled, candidate, scan
from backend.schemas import (
    ExportInput,
    FavoriteInput,
    GamePatch,
    ImportInput,
    ProviderInput,
    ScanInput,
    SettingsInput,
)

logger = logging.getLogger("rlm")


def serialize(model):
    return jsonable_encoder({column.name: getattr(model, column.name) for column in model.__table__.columns})


def create_app(data_dir: Path = DATA) -> FastAPI:
    engine = make_engine(data_dir)
    session_factory = sessions(engine)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rlm-worker")
    mutation_lock = RLock()
    acquisition = Acquisition(session_factory, data_dir, mutation_lock)
    devices = DeviceService(session_factory, mutation_lock)
    intelligence = Intelligence(session_factory, data_dir, mutation_lock, devices)
    devices.game_guard = intelligence.prepare_games
    collections = Collections(session_factory, intelligence, mutation_lock)
    media = MediaService(session_factory, data_dir, acquisition, intelligence, mutation_lock)
    devices.collection_guard = collections.prepare_sync
    installations = Installations(
        session_factory, data_dir, mutation_lock, devices, acquisition, intelligence, collections, media
    )

    @asynccontextmanager
    async def lifespan(app):
        config = Config(str(PROJECT / "alembic.ini"))
        config.attributes["engine"] = engine
        command.upgrade(config, "head")
        collections.start()
        handler = RotatingFileHandler(
            data_dir / "application.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        with session_factory.begin() as db:
            for job in db.scalars(select(Job).where(Job.status.in_(["queued", "running", "cancelling"]))):
                job.status = "failed"
                job.error = "Operazione interrotta dal riavvio. Ripetere l'operazione."
        acquisition.start()
        devices.start()
        intelligence.start()
        installations.start()
        yield
        installations.shutdown()
        devices.shutdown()
        intelligence.shutdown()
        acquisition.shutdown()
        executor.shutdown(wait=True)
        engine.dispose()
        logger.removeHandler(handler)
        handler.close()

    app = FastAPI(title="RetroPie Library Manager", version="0.8.0", lifespan=lifespan)
    app.state.sessions = session_factory
    app.state.acquisition = acquisition
    app.state.devices = devices
    app.state.intelligence = intelligence
    app.state.collections = collections
    app.state.media = media
    app.state.installations = installations
    app.include_router(installation_routes(installations))
    app.include_router(collections.router)
    app.include_router(media.router)
    app.include_router(intelligence.router)
    app.include_router(acquisition.router)
    access = Access(data_dir)
    app.state.access = access
    app.include_router(access.routes())
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-RLM-Request", "X-Chunk-SHA256", "X-RLM-CSRF"],
    )
    app.middleware("http")(access.guard)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        if request.url.path.startswith("/api/access/"):
            return JSONResponse({"detail": "Campi di accesso non validi"}, status_code=422)
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(ValueError)
    async def invalid_input(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(OSError)
    async def filesystem_error(request, exc):
        logger.exception("Filesystem operation failed")
        return JSONResponse({"detail": "Percorso non accessibile o spazio insufficiente"}, status_code=400)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logger.exception("Unexpected request failure")
        return JSONResponse({"detail": "Errore interno. Consultare application.log."}, status_code=500)

    def settings():
        with session_factory() as db:
            value = db.get(Setting, "library")
            return value.value if value else SettingsInput().model_dump()

    def providers():
        with session_factory() as db:
            value = db.get(Setting, "providers")
            return value.value if value else []

    def submit(kind, operation, cancellable=False):
        job_id = str(uuid4())
        with session_factory.begin() as db:
            db.add(Job(id=job_id, kind=kind, status="queued"))

        checked_at = 0.0

        def checkpoint(progress=None):
            nonlocal checked_at
            current = time.monotonic()
            if current - checked_at < 0.15:
                return
            checked_at = current
            with session_factory.begin() as db:
                job = db.get(Job, job_id)
                if job.status == "cancelling":
                    raise ScanCancelled("Scansione annullata: nessun file importato o modificato")
                if progress:
                    job.result = {"progress": progress}

        def run():
            try:
                if cancellable:
                    checkpoint()
                with session_factory.begin() as db:
                    current_job = db.get(Job, job_id)
                    if cancellable and current_job.status == "cancelling":
                        raise ScanCancelled("Scansione annullata")
                    current_job.status = "running"
                result = operation(checkpoint) if cancellable else operation()
                with session_factory.begin() as db:
                    job = db.get(Job, job_id)
                    if cancellable and job.status == "cancelling":
                        raise ScanCancelled("Scansione annullata")
                    job.result = result
                    job.status = "completed"
                logger.info("Job %s %s completed", kind, job_id)
            except Exception as exc:
                logger.exception("Job %s %s failed", kind, job_id)
                with session_factory.begin() as db:
                    job = db.get(Job, job_id)
                    job.status = "cancelled" if isinstance(exc, ScanCancelled) else "failed"
                    job.error = str(exc)

        executor.submit(run)
        return {"id": job_id, "status": "queued"}

    def require_game(db, game_id):
        game = db.get(Game, game_id)
        if not game:
            raise HTTPException(404, "Gioco non trovato")
        return game

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": app.version}

    @app.get("/api/platforms")
    def platforms():
        return PLATFORMS

    @app.get("/api/settings")
    def get_settings():
        return {**settings(), "data_dir": str(data_dir)}

    @app.put("/api/settings")
    def save_settings(body: SettingsInput):
        roots = [str(local_path(root)) for root in body.import_roots]
        if any(not Path(root).is_dir() for root in roots):
            raise ValueError("Le sorgenti devono essere cartelle esistenti")
        export = str(local_path(body.export_root)) if body.export_root else ""
        if export and not Path(export).is_dir():
            raise ValueError("La destinazione deve essere una cartella esistente")
        value = {"import_roots": list(dict.fromkeys(roots)), "export_root": export}
        with mutation_lock, session_factory.begin() as db:
            db.merge(Setting(key="library", value=value))
        return value

    @app.get("/api/stats")
    def stats():
        with session_factory() as db:
            return {
                "games": db.scalar(select(func.count(Game.id))),
                "bytes": db.scalar(select(func.coalesce(func.sum(Game.size), 0))),
                "favorites": db.scalar(select(func.count(Game.id)).where(Game.favorite.is_(True))),
                "platforms": dict(
                    db.execute(select(Game.platform, func.count(Game.id)).group_by(Game.platform)).all()
                ),
            }

    @app.get("/api/games")
    def games(
        q: str = Query("", max_length=300),
        platform: str = "",
        favorite: bool = False,
        region: str = "",
        genre: str = "",
        page: int = Query(1, ge=1),
        page_size: int = Query(36, ge=1, le=200),
    ):
        query = select(Game)
        if q:
            query = query.where(Game.title.icontains(q, autoescape=True))
        if platform:
            query = query.where(Game.platform == platform)
        if favorite:
            query = query.where(Game.favorite.is_(True))
        if region:
            query = query.where(Game.region == region)
        if genre:
            query = query.where(Game.genre == genre)
        with session_factory() as db:
            total = db.scalar(select(func.count()).select_from(query.subquery()))
            items = db.scalars(
                query.order_by(Game.title, Game.id).offset((page - 1) * page_size).limit(page_size)
            )
            return {"total": total, "items": [serialize(g) for g in items], "page": page}

    @app.get("/api/games/{game_id}")
    def game_detail(game_id: int):
        with session_factory() as db:
            return serialize(require_game(db, game_id))

    @app.patch("/api/games/{game_id}/favorite")
    def favorite(game_id: int, body: FavoriteInput):
        with mutation_lock, session_factory.begin() as db:
            game = require_game(db, game_id)
            game.favorite = body.favorite
            return serialize(game)

    @app.put("/api/games/{game_id}")
    def edit_game(game_id: int, body: GamePatch):
        if body.cover_path:
            cover = allowed(
                body.cover_path,
                [*settings()["import_roots"], str(data_dir / "covers"), str(data_dir / "media")],
            )
            if (
                cover.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}
                or cover.stat().st_size > 20_000_000
            ):
                raise ValueError("Copertina PNG/JPG/WebP, massimo 20 MB")
        with mutation_lock, session_factory.begin() as db:
            game = require_game(db, game_id)
            for key, value in body.model_dump().items():
                if key in {"author", "publisher"} and key not in body.model_fields_set:
                    continue
                setattr(game, key, value)
            return serialize(game)

    @app.get("/api/games/{game_id}/cover")
    def cover(game_id: int):
        with session_factory() as db:
            game = require_game(db, game_id)
            if not game.cover_path:
                raise HTTPException(404, "Copertina assente")
            return FileResponse(
                allowed(
                    game.cover_path,
                    [*settings()["import_roots"], str(data_dir / "covers"), str(data_dir / "media")],
                )
            )

    @app.post("/api/imports/scan", status_code=202)
    def start_scan(body: ScanInput):
        root = allowed(body.root, settings()["import_roots"])
        if not root.is_dir():
            raise ValueError("Selezionare una cartella")

        def operation(checkpoint):
            with session_factory() as db:
                known = set(db.scalars(select(Game.sha256)))
            return scan(root, body.platform, known, checkpoint)

        return submit("scan", operation, cancellable=True)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_scan(job_id: str):
        with session_factory.begin() as db:
            job = db.get(Job, job_id)
            if not job or job.kind != "scan" or job.status not in {"queued", "running"}:
                raise ValueError("Scansione non annullabile")
            job.status = "cancelling"
        return {"ok": True}

    @app.post("/api/imports/{job_id}/commit", status_code=202)
    def commit_import(job_id: str, body: ImportInput):
        def operation():
            with mutation_lock, session_factory.begin() as db:
                job = db.get(Job, job_id)
                if not job or job.kind != "scan" or job.status != "completed":
                    raise ValueError("Anteprima non disponibile")
                candidates = {c["id"]: c for c in job.result["candidates"]}
                if not set(body.candidate_ids).issubset(candidates):
                    raise ValueError("Selezione non valida")
                imported = 0
                skipped = 0
                for candidate_id in dict.fromkeys(body.candidate_ids):
                    item = candidates[candidate_id]
                    _, duplicate = import_candidate(
                        db, item, settings()["import_roots"], body.provenance, body.license
                    )
                    skipped += int(duplicate)
                    imported += int(not duplicate)
            return {"imported": imported, "skipped": skipped}

        return submit("import", operation)

    @app.get("/api/jobs")
    def jobs():
        with session_factory() as db:
            return [
                {"id": j.id, "kind": j.kind, "status": j.status, "error": j.error, "created_at": j.created_at}
                for j in db.scalars(select(Job).order_by(Job.created_at.desc()).limit(30))
            ]

    @app.get("/api/jobs/{job_id}")
    def job_detail(job_id: str):
        with session_factory() as db:
            job = db.get(Job, job_id)
            if not job:
                raise HTTPException(404, "Operazione non trovata")
            return serialize(job)

    @app.post("/api/exports", status_code=202)
    def export(body: ExportInput):
        destination = local_path(settings()["export_root"])

        def operation():
            with session_factory() as db:
                selected = list(db.scalars(select(Game).where(Game.id.in_(body.game_ids)).order_by(Game.id)))
                if len(selected) != len(set(body.game_ids)):
                    raise ValueError("La selezione contiene giochi inesistenti")
                intelligence.prepare_games(selected)
                result = LocalTransport().publish(selected, destination, body.dry_run)
                capacity = acquisition.storage()
                capacity["selection_fits_target"] = result["required_bytes"] <= capacity["usable_bytes"]
                result["target_capacity"] = capacity
                return result

        return submit("export", operation)

    @app.get("/api/providers")
    def get_providers():
        return providers()

    @app.put("/api/providers/{provider_id}")
    def save_provider(provider_id: str, body: ProviderInput):
        if provider_id != body.id or len({e.id for e in body.entries}) != len(body.entries):
            raise ValueError("Identificatori provider/gioco non validi o duplicati")
        with mutation_lock, session_factory.begin() as db:
            current = [p for p in providers() if p["id"] != body.id]
            db.merge(Setting(key="providers", value=[*current, body.model_dump()]))
        acquisition.sync_manifests()
        return body

    @app.post("/api/providers/{provider_id}/download/{entry_id}", status_code=202)
    def start_download(provider_id: str, entry_id: str):
        provider = next((p for p in providers() if p["id"] == provider_id), None)
        if not provider:
            raise HTTPException(404, "Provider non trovato")
        entry = next(
            (e for e in ManifestProvider(ProviderInput(**provider)).catalog() if e.id == entry_id), None
        )
        if not entry:
            raise HTTPException(404, "Download non trovato")

        def operation():
            path = download(entry, data_dir / "downloads")
            item = candidate([path], path.parent, entry.platform)
            with mutation_lock, session_factory.begin() as db:
                existing = db.scalar(select(Game).where(Game.sha256 == item["sha256"]))
                if existing:
                    return {"game_id": existing.id, "duplicate": True}
                item.pop("entrypoints")
                item["title"] = entry.title
                game = Game(
                    **item, license=entry.license, provenance=f"{provider['name']} | {entry.rights_url}"
                )
                db.add(game)
                db.flush()
                return {"game_id": game.id, "duplicate": False}

        return submit("download", operation)

    @app.post("/api/metadata/enrich", status_code=202)
    def enrich_metadata(body: EnrichInput):
        return submit("metadata", lambda: acquisition.enrich(body))

    app.include_router(devices.routes(submit))

    frontend = PROJECT / "frontend" / "dist"
    if frontend.exists():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
