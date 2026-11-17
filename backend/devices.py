import logging
import os
import subprocess
import sys
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import paramiko
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from backend.acquisition import fingerprint, record
from backend.config import PROJECT
from backend.db import Device, Game, SyncPresence, SyncRun
from backend.remote_fs import diagnostics
from backend.ssh_connection import SSHConnection, ensure_key, probe, trust
from backend.sync_engine import SyncCancelled, build_plan, perform_sync
from backend.sync_schemas import DeviceInput, SyncConfirm, SyncControl, SyncInput, TrustInput

logger = logging.getLogger("rlm")
BUSY = {"preparing", "queued", "running", "cancelling", "retry_wait"}


class DeviceService:
    def __init__(self, sessions, lock):
        self.sessions = sessions
        self.lock = lock
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sftp-sync")
        self.stop = threading.Event()
        self.connect = SSHConnection
        self.game_guard: Callable[..., list] = lambda games, config, connection: []
        self.collection_guard: Callable[..., str] = lambda games, options: ""

    def start(self):
        with self.sessions.begin() as db:
            for run in db.scalars(select(SyncRun).where(SyncRun.status.in_(BUSY))):
                run.status = "failed"
                run.error = (
                    "Interrotto dal riavvio. Retry esplicito; parziali verificati prima della ripresa."
                )

    def shutdown(self):
        self.stop.set()
        self.pool.shutdown(wait=True)

    def get_device(self, device_id):
        with self.sessions() as db:
            device = db.get(Device, device_id)
            if not device:
                raise HTTPException(404, "Dispositivo non trovato")
            return {**device.config, "fingerprint": device.fingerprint}

    def diagnose(self, device_id):
        try:
            config = self.get_device(device_id)
            with self.connect(config) as connection:
                result = diagnostics(connection, config)
            with self.sessions.begin() as db:
                device = db.get(Device, device_id)
                device.status = "online"
                device.diagnostics = result
                device.error = ""
            return result
        except Exception as exc:
            with self.sessions.begin() as db:
                device = db.get(Device, device_id)
                if device:
                    device.status = "offline"
                    device.error = str(exc)
            raise

    def prepare(self, body):
        run_id = str(uuid4())
        with self.sessions.begin() as db:
            if not db.get(Device, body.device_id):
                raise HTTPException(404, "Dispositivo non trovato")
            db.add(SyncRun(id=run_id, device_id=body.device_id))

        def work():
            try:
                config = self.get_device(body.device_id)
                with self.sessions() as db:
                    games = list(db.scalars(select(Game).where(Game.id.in_(body.game_ids)).order_by(Game.id)))
                    if len(games) != len(set(body.game_ids)):
                        raise ValueError("La selezione contiene giochi non trovati")
                library_fingerprint = self.collection_guard(games, body)
                with self.connect(config) as connection:
                    arcade = self.game_guard(games, {**config, "device_id": body.device_id}, connection)
                    plan = build_plan(connection, config, games, body)
                    plan["arcade"] = arcade
                    plan["library_fingerprint"] = library_fingerprint
                plan["device_fingerprint"] = fingerprint(config)
                with self.sessions.begin() as db:
                    run = db.get(SyncRun, run_id)
                    run.plan = plan
                    if run.status == "cancelling":
                        run.status = "cancelled"
                    else:
                        run.status = "preview"
            except Exception as exc:
                self.failure(run_id, exc)

        self.pool.submit(work)
        return {"id": run_id}

    def failure(self, run_id, exc):
        logger.warning("Sync %s: %s", run_id, str(exc))
        with self.sessions.begin() as db:
            run = db.get(SyncRun, run_id)
            run.status = "failed"
            run.error = str(exc)

    def checkpoint(self, run_id, progress):
        with self.sessions.begin() as db:
            run = db.get(SyncRun, run_id)
            if run.status == "cancelling":
                raise SyncCancelled()
            if self.stop.is_set():
                raise ValueError("Server arrestato: parziali conservati per il retry")
            if "report" in progress:
                run.report = progress["report"]
            run.progress = {key: value for key, value in progress.items() if key != "report"}

    def execute(self, run_id):
        for attempt in range(1, 4):
            try:
                with self.sessions.begin() as db:
                    run = db.get(SyncRun, run_id)
                    if run.status == "cancelling":
                        raise SyncCancelled()
                    run.status = "running"
                    plan = run.plan
                    device_id = run.device_id
                current = self.get_device(device_id)
                if fingerprint(current) != plan["device_fingerprint"]:
                    raise ValueError("Configurazione cambiata: preparare una nuova anteprima")
                with self.connect(current) as connection:
                    with self.sessions() as db:
                        selected = list(
                            db.scalars(select(Game).where(Game.id.in_([g["id"] for g in plan["groups"]])))
                        )
                    arcade = self.game_guard(selected, {**current, "device_id": device_id}, connection)
                    if self.collection_guard(selected, SyncInput(**plan["options"])) != plan.get(
                        "library_fingerprint", ""
                    ):
                        raise ValueError("Raccolta o metadati cambiati dopo l'anteprima")
                    if fingerprint(arcade) != fingerprint(plan.get("arcade", [])):
                        raise ValueError("Compatibilità arcade cambiata dopo il dry-run")
                    result = perform_sync(
                        connection,
                        plan,
                        run_id,
                        lambda progress, attempt=attempt: self.checkpoint(
                            run_id, {**progress, "attempt": attempt}
                        ),
                    )
                with self.sessions.begin() as db:
                    run = db.get(SyncRun, run_id)
                    run.status = "completed"
                    run.report = result
                    run.error = ""
                    for group in plan["groups"]:
                        game = db.get(Game, group["id"])
                        if game:
                            presence = db.scalar(
                                select(SyncPresence).where(
                                    SyncPresence.game_id == game.id, SyncPresence.device_id == device_id
                                )
                            )
                            if not presence:
                                presence = SyncPresence(game_id=game.id, device_id=device_id)
                                db.add(presence)
                            presence.sha256 = game.sha256
                            presence.run_id = run_id
                try:
                    self.diagnose(device_id)
                except Exception:
                    logger.warning("Diagnostica finale non disponibile per %s", device_id)
                return
            except SyncCancelled:
                with self.sessions.begin() as db:
                    run = db.get(SyncRun, run_id)
                    run.status = "cancelled"
                    run.error = "Annullato. I gruppi già verificati e pubblicati rimangono sul dispositivo."
                return
            except (OSError, paramiko.SSHException, EOFError) as exc:
                if attempt == 3 or isinstance(
                    exc, (paramiko.AuthenticationException, paramiko.BadHostKeyException)
                ):
                    self.failure(run_id, exc)
                    return
                with self.sessions.begin() as db:
                    run = db.get(SyncRun, run_id)
                    if run.status != "cancelling":
                        run.status = "retry_wait"
                    run.error = str(exc)
                if self.stop.wait(2**attempt):
                    self.failure(run_id, ValueError("Interrotto durante il retry"))
                    return
            except Exception as exc:
                self.failure(run_id, exc)
                return

    def routes(self, submit):
        router = APIRouter(prefix="/api")

        def require_idle(db, device_id):
            if db.scalar(select(SyncRun.id).where(SyncRun.device_id == device_id, SyncRun.status.in_(BUSY))):
                raise ValueError("Dispositivo impegnato: attendere o annullare la sincronizzazione")

        @router.get("/devices")
        def devices():
            with self.sessions() as db:
                return [record(d) for d in db.scalars(select(Device))]

        @router.post("/devices", status_code=201)
        def create(body: DeviceInput):
            device_id = str(uuid4())
            with self.lock, self.sessions.begin() as db:
                if body.is_default:
                    for other in db.scalars(select(Device)):
                        other.is_default = False
                db.add(
                    Device(
                        id=device_id,
                        config=body.model_dump(exclude={"is_default"}),
                        is_default=body.is_default,
                    )
                )
            return {"id": device_id}

        @router.put("/devices/{device_id}")
        def update(device_id: str, body: DeviceInput):
            with self.lock, self.sessions.begin() as db:
                require_idle(db, device_id)
                device = db.get(Device, device_id)
                if not device:
                    raise HTTPException(404, "Dispositivo non trovato")
                if any(device.config[k] != getattr(body, k) for k in ("host", "port", "username")):
                    device.fingerprint = ""
                    device.status = "unknown"
                    device.diagnostics = {}
                if body.is_default:
                    for other in db.scalars(select(Device)):
                        other.is_default = False
                device.config = body.model_dump(exclude={"is_default"})
                device.is_default = body.is_default
            return {"ok": True}

        @router.delete("/devices/{device_id}")
        def delete(device_id: str):
            with self.lock, self.sessions.begin() as db:
                require_idle(db, device_id)
                device = db.get(Device, device_id)
                if not device:
                    raise HTTPException(404, "Dispositivo non trovato")
                db.delete(device)
            return {"ok": True}

        @router.post("/devices/{device_id}/probe")
        def inspect_host(device_id: str):
            config = self.get_device(device_id)
            try:
                return probe(config["host"], config["port"])
            except (OSError, paramiko.SSHException) as exc:
                raise ValueError("Connessione SSH/Ed25519 non verificabile: " + str(exc)) from exc

        @router.post("/devices/{device_id}/trust")
        def trust_host(device_id: str, body: TrustInput):
            config = self.get_device(device_id)
            result = trust(config["host"], config["port"], body.fingerprint)
            with self.sessions.begin() as db:
                db.get(Device, device_id).fingerprint = result["fingerprint"]
            return result

        @router.post("/devices/{device_id}/key-setup")
        def setup(device_id: str):
            config = self.get_device(device_id)
            if not config["fingerprint"]:
                raise ValueError("Confermare prima la fingerprint")
            key = ensure_key()
            if os.name != "nt":
                raise ValueError("Assistente interattivo disponibile su Windows")
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "backend.ssh_setup",
                    "--host",
                    config["host"],
                    "--port",
                    str(config["port"]),
                    "--username",
                    config["username"],
                    "--fingerprint",
                    config["fingerprint"],
                ],
                cwd=PROJECT,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            return {
                "message": "Inserire la password soltanto nel terminale SSH aperto sul PC. Poi eseguire Test SSH e diagnostica.",
                "key_fingerprint": key["fingerprint"],
            }

        @router.post("/devices/{device_id}/diagnostics", status_code=202)
        def inspect(device_id: str):
            self.get_device(device_id)
            return submit("diagnostics", lambda: self.diagnose(device_id))

        @router.post("/sync/plans", status_code=202)
        def preview(body: SyncInput):
            return self.prepare(body)

        @router.get("/sync/runs")
        def runs():
            with self.sessions() as db:
                return [
                    record(run)
                    for run in db.scalars(select(SyncRun).order_by(SyncRun.created_at.desc()).limit(50))
                ]

        @router.get("/sync/runs/{run_id}")
        def get_run(run_id: str):
            with self.sessions() as db:
                run = db.get(SyncRun, run_id)
                if not run:
                    raise HTTPException(404, "Sincronizzazione non trovata")
                return record(run)

        @router.post("/sync/runs/{run_id}/confirm")
        def confirm(run_id: str, body: SyncConfirm):
            with self.lock, self.sessions.begin() as db:
                run = db.get(SyncRun, run_id)
                if not run:
                    raise HTTPException(404, "Sincronizzazione non trovata")
                if run.status != "preview" or not run.plan.get("can_sync"):
                    raise ValueError("Anteprima non confermabile")
                require_idle(db, run.device_id)
                if run.plan["media"] and not body.media_rights_confirmed:
                    raise ValueError("Confermare i diritti sulle copertine selezionate")
                run.plan = {**run.plan, "authorization": body.model_dump()}
                run.status = "queued"
            self.pool.submit(self.execute, run_id)
            return {"id": run_id}

        @router.post("/sync/runs/{run_id}/control")
        def control(run_id: str, body: SyncControl):
            with self.lock, self.sessions.begin() as db:
                run = db.get(SyncRun, run_id)
                if not run:
                    raise HTTPException(404, "Sincronizzazione non trovata")
                if body.action == "cancel" and run.status in BUSY:
                    run.status = "cancelling"
                elif (
                    body.action == "retry"
                    and run.status in {"failed", "cancelled"}
                    and run.plan.get("authorization")
                ):
                    require_idle(db, run.device_id)
                    run.status = "queued"
                    run.error = ""
                else:
                    raise ValueError("Azione non disponibile nello stato corrente")
            if body.action == "retry":
                self.pool.submit(self.execute, run_id)
            return {"ok": True}

        return router
