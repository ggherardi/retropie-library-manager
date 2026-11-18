"""Local-only installation API, including bounded resumable browser uploads."""

import asyncio
import hashlib
import os
import re
import shutil
from pathlib import PurePosixPath
from uuid import uuid4

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from backend.acquisition import record
from backend.db import Device, InstallationBatch, InstallationItem, InstallationUpload, Setting
from backend.installation_schemas import (
    InstallationConfirm,
    InstallationControl,
    InstallationDecision,
    LocalInstallInput,
    UploadInstallInput,
    VisibilityInput,
)
from backend.paths import allowed, digest

CHUNK_LIMIT = 8 * 1024**2
BATCH_LIMIT = 32 * 1024**3


def upload_relative(value):
    path = PurePosixPath(value.replace("\\", "/"))
    if (
        path.is_absolute()
        or not path.parts
        or any(
            p in {".", ".."}
            or p.endswith((".", " "))
            or re.search(r'[<>:"|?*\x00-\x1f]', p)
            or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", p)
            for p in path.parts
        )
    ):
        raise ValueError("Nome/percorso upload non sicuro")
    return path.as_posix()


def routes(service):
    router = APIRouter(prefix="/api/installations")
    locks: dict[str, asyncio.Lock] = {}

    @router.get("")
    def dashboard():
        with service.sessions() as db:
            batches = list(
                db.scalars(select(InstallationBatch).order_by(InstallationBatch.created_at.desc()).limit(50))
            )
            devices = [record(d) for d in db.scalars(select(Device))]
            summaries = []
            for batch in batches:
                from collections import Counter

                counts = Counter(
                    db.scalars(select(InstallationItem.status).where(InstallationItem.batch_id == batch.id))
                )
                summaries.append(
                    {
                        "id": batch.id,
                        "mode": batch.mode,
                        "status": batch.status,
                        "control": batch.control,
                        "created_at": batch.created_at,
                        "authorized": batch.authorized,
                        "counts": dict(counts),
                        "total": sum(counts.values()),
                    }
                )
        return {"batches": summaries, "devices": devices}

    @router.get("/sources")
    def sources(path: str = ""):
        with service.sessions() as db:
            setting = db.get(Setting, "library")
            roots = setting.value.get("import_roots", []) if setting else []
        if (service.data / "downloads").is_dir():
            roots = [*roots, str(service.data / "downloads")]
        if not path:
            return {"roots": roots, "items": []}
        directory = allowed(path, roots)
        if not directory.is_dir():
            raise ValueError("Selezionare una cartella autorizzata")
        items = []
        for child in directory.iterdir():
            if child.is_symlink():
                continue
            try:
                child = allowed(str(child), roots)
            except ValueError:
                continue
            items.append({"name": child.name, "path": str(child), "directory": child.is_dir()})
            if len(items) >= 2000:
                break
        return {
            "roots": roots,
            "path": str(directory),
            "items": sorted(items, key=lambda i: (not i["directory"], i["name"].casefold())),
        }

    @router.post("/local", status_code=202)
    def local(body: LocalInstallInput):
        return service.create(body)

    @router.post("/uploads", status_code=201)
    def uploads(body: UploadInstallInput):
        relatives = [upload_relative(f.relative) for f in body.files]
        if len(set(p.casefold() for p in relatives)) != len(relatives):
            raise ValueError("Nomi duplicati nella selezione (anche maiuscole/minuscole)")
        names = {p.casefold() for p in relatives}
        for name in relatives:
            if any(
                parent.as_posix().casefold() in names
                for parent in PurePosixPath(name).parents
                if str(parent) != "."
            ):
                raise ValueError("Conflitto file/cartella nella selezione")
        total = sum(f.size for f in body.files)
        if total > BATCH_LIMIT:
            raise ValueError("Upload oltre 32 GiB: usare le cartelle autorizzate del PC")
        if total + 1024**3 > shutil.disk_usage(service.data).free:
            raise ValueError("Spazio PC insufficiente per conservare una copia della selezione")
        batch = service.create(body, upload=True)
        root = service.data / "inbox" / batch["id"]
        if not root.resolve().is_relative_to(service.data.resolve()):
            raise ValueError("Cartella upload fuori dall'archivio locale")
        root.mkdir(parents=True, exist_ok=True)
        with service.lock, service.sessions.begin() as db:
            if not db.scalar(select(InstallationUpload.id).where(InstallationUpload.batch_id == batch["id"])):
                for descriptor, relative in zip(body.files, relatives, strict=True):
                    db.add(
                        InstallationUpload(
                            id=str(uuid4()), batch_id=batch["id"], relative=relative, size=descriptor.size
                        )
                    )
        return service.detail(batch["id"])

    @router.put("/{batch_id}/uploads/{upload_id}")
    async def chunk(batch_id: str, upload_id: str, request: Request, offset: int = Query(ge=0)):
        expected = request.headers.get("X-Chunk-SHA256", "")
        if not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ValueError("SHA-256 del blocco richiesto")
        lock = locks.setdefault(upload_id, asyncio.Lock())
        async with lock:
            with service.sessions() as db:
                upload = db.get(InstallationUpload, upload_id)
                batch = db.get(InstallationBatch, batch_id)
                if (
                    not upload
                    or upload.batch_id != batch_id
                    or not batch
                    or batch.status != "draft"
                    or batch.control != "run"
                ):
                    raise ValueError("Upload non disponibile in questo stato")
            data = bytearray()
            async for block in request.stream():
                data.extend(block)
                if len(data) > CHUNK_LIMIT:
                    raise ValueError("Blocco oltre 8 MiB")
            if hashlib.sha256(data).hexdigest() != expected or offset + len(data) > upload.size:
                raise ValueError("Hash o dimensione del blocco non corrispondente")
            root = (service.data / "inbox" / batch_id).resolve()
            if not root.is_relative_to(service.data.resolve()):
                raise ValueError("Cartella upload fuori dall'archivio locale")
            target = root / upload.relative
            partial = root / (upload_id + ".partial")
            if (
                not target.resolve().is_relative_to(root)
                or not partial.resolve().is_relative_to(root)
                or target.is_symlink()
                or partial.is_symlink()
            ):
                raise ValueError("Destinazione upload non sicura")
            if offset != upload.received or upload.status == "complete":
                saved = upload.chunks.get(str(offset))
                if saved == {"size": len(data), "sha256": expected}:
                    return record(upload)
                raise ValueError("Offset o contenuto cambiato: riselezionare gli stessi file per riprendere")
            if not data and upload.size:
                raise ValueError("Blocco vuoto")
            received = offset + len(data)
            # Recover the narrow crash window between atomic rename and receipt commit.
            if target.exists():
                if received != upload.size or target.stat().st_size != upload.size:
                    raise ValueError("Conflitto upload: nessuna sovrascrittura")

                def recover():
                    with target.open("rb") as stream:
                        for start, saved in upload.chunks.items():
                            stream.seek(int(start))
                            if hashlib.sha256(stream.read(saved["size"])).hexdigest() != saved["sha256"]:
                                raise ValueError("Contenuto upload cambiato dopo l'interruzione")
                        stream.seek(offset)
                        if stream.read(len(data)) != data:
                            raise ValueError("Blocco finale differente dopo l'interruzione")
                    return digest(target)

                sha = await asyncio.to_thread(recover)
            else:
                if partial.exists() and partial.stat().st_size < upload.received:
                    raise ValueError("Parziale upload mancante: creare una nuova selezione")
                if not partial.exists() and upload.received:
                    raise ValueError("Parziale upload perso: creare una nuova selezione")
                if shutil.disk_usage(root).free < len(data) + 64 * 1024**2:
                    raise ValueError("Spazio PC insufficiente")
                # A crash may leave an uncommitted tail. Only this owned partial is truncated.
                with partial.open("r+b" if partial.exists() else "wb") as stream:
                    stream.truncate(upload.received)
                    stream.seek(upload.received)
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                sha = await asyncio.to_thread(digest, partial) if received == upload.size else ""
                if received == upload.size:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        raise ValueError("Conflitto upload: nessuna sovrascrittura")
                    partial.rename(target)
            with service.sessions.begin() as db:
                current = db.get(InstallationUpload, upload_id)
                current.received, current.sha256 = received, sha
                current.chunks = {**current.chunks, str(offset): {"size": len(data), "sha256": expected}}
                current.status = "complete" if received == current.size else "uploading"
                db.flush()
                return record(current)

    @router.post("/{batch_id}/analyze", status_code=202)
    def analyze(batch_id: str):
        with service.lock, service.sessions.begin() as db:
            batch = db.get(InstallationBatch, batch_id)
            if not batch or batch.status != "draft":
                raise ValueError("Selezione non disponibile per l'analisi")
            uploads = list(
                db.scalars(select(InstallationUpload).where(InstallationUpload.batch_id == batch_id))
            )
            if not uploads or any(u.status != "complete" for u in uploads):
                raise ValueError("Completare tutti gli upload prima dell'analisi")
            batch.status = "queued"
        service.wake.set()
        return {"id": batch_id}

    @router.get("/{batch_id}")
    def detail(batch_id: str, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100)):
        return service.detail(batch_id, page, page_size)

    @router.post("/{batch_id}/confirm")
    def confirm(batch_id: str, body: InstallationConfirm):
        return service.confirm(batch_id, body)

    @router.post("/{batch_id}/control")
    def control(batch_id: str, body: InstallationControl):
        return service.control(batch_id, body.action)

    @router.post("/items/{item_id}/decision")
    def decision(item_id: str, body: InstallationDecision):
        return service.decision(item_id, body)

    @router.post("/items/{item_id}/retry")
    def retry(item_id: str):
        service.retry_item(item_id)
        return {"ok": True}

    @router.post("/items/{item_id}/visible")
    def visible(item_id: str, body: VisibilityInput):
        with service.sessions.begin() as db:
            item = db.get(InstallationItem, item_id)
            if not item or item.status != "installed":
                raise ValueError("Prima completare la verifica dei file e dei metadati")
            item.visibility = "operator_confirmed"
        return {"ok": True}

    return router
