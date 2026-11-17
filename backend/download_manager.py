import hashlib
import json
import logging
import re
import shutil
import stat
import threading
import time
import zipfile
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx
from sqlalchemy import select

from backend.db import DiscoveryEntry, DownloadTask, Game, Setting
from backend.discovery_sources import supported_download
from backend.network import PublicHTTP
from backend.paths import digest
from backend.scanner import candidate

ACTIVE = {"queued", "running", "verifying", "retry_wait", "paused", "downloaded"}
logger = logging.getLogger("rlm")


class Interrupted(Exception):
    pass


class Retryable(Exception):
    def __init__(self, message, delay=0):
        super().__init__(message)
        self.delay = delay


def validate_archive(path: Path):
    if path.suffix.lower() != ".zip":
        return
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 2000 or sum(e.file_size for e in entries) > 2 * 1024**3:
            raise ValueError("Archivio troppo grande dopo decompressione")
        for entry in entries:
            name = entry.filename.replace("\\", "/")
            if name.startswith("/") or ".." in Path(name).parts or ":" in name:
                raise ValueError("Archivio con path traversal")
            if stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
                raise ValueError("Archivio con link simbolici o cifratura")
            if entry.file_size > max(entry.compress_size, 1) * 1000:
                raise ValueError("Rapporto di compressione non sicuro")
            with archive.open(entry) as content:
                while content.read(65536):
                    pass  # ZIP checks CRC while reading, without extracting files.


class DownloadManager:
    def __init__(self, sessions, data_dir: Path, lock, http: PublicHTTP):
        self.sessions = sessions
        self.data_dir = data_dir
        self.lock = lock
        self.http = http
        self.stop = threading.Event()
        self.pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="download")
        self.active: dict[str, Future] = {}
        self.thread: threading.Thread | None = None
        self.cover_loader: Callable[[dict], Path] | None = None

    def start(self):
        with self.sessions.begin() as db:
            for task in db.scalars(
                select(DownloadTask).where(DownloadTask.status.in_(["running", "verifying", "downloaded"]))
            ):
                task.status = "paused"
                task.error = "Interrotto dal riavvio. Riprendere per verificare i dati parziali."
        self.thread = threading.Thread(target=self.schedule, daemon=True)
        self.thread.start()

    def shutdown(self):
        self.stop.set()
        if self.thread:
            self.thread.join()
        self.pool.shutdown(wait=True)

    def schedule(self):
        while not self.stop.wait(0.25):
            try:
                self.tick()
            except Exception:
                logger.exception("Download scheduler failure")

    def tick(self):
        with self.lock:
            self.active = {key: future for key, future in self.active.items() if not future.done()}
            with self.sessions.begin() as db:
                config = db.get(Setting, "acquisition")
                concurrency = config.value.get("concurrency", 2) if config else 2
                slots = max(0, concurrency - len(self.active))
                pending = list(
                    db.scalars(
                        select(DownloadTask)
                        .where(
                            DownloadTask.status.in_(["queued", "retry_wait"]),
                            DownloadTask.retry_at <= time.time(),
                        )
                        .order_by(DownloadTask.created_at)
                    )
                )
                chosen = [task for task in pending if task.id not in self.active][:slots]
                for task in chosen:
                    task.status = "running"
                    task.attempts += 1
            for task in chosen:
                self.active[task.id] = self.pool.submit(self.run, task.id)

    def checkpoint(self, task_id, received=None, **updates):
        with self.lock, self.sessions.begin() as db:
            task = db.get(DownloadTask, task_id)
            if self.stop.is_set():
                if task.status not in {"cancelled", "paused"}:
                    task.status = "paused"
                db.flush()
                interrupted = True
            else:
                interrupted = task.status in {"paused", "cancelled"}
            if received is not None:
                task.received = received
            if not interrupted:
                for key, value in updates.items():
                    setattr(task, key, value)
        if interrupted:
            raise Interrupted()

    def directory(self, task_id):
        return self.data_dir / "downloads" / task_id

    def control(self, task_id, action):
        with self.lock, self.sessions.begin() as db:
            task = db.get(DownloadTask, task_id)
            if not task:
                raise ValueError("Download non trovato")
            if task.status == "imported":
                raise ValueError("Download già importato")
            if action == "pause" and task.status in ACTIVE:
                task.status = "paused"
            elif action == "cancel":
                task.status = "cancelled"
            elif action in {"resume", "retry"} and task.status in {
                "paused",
                "failed",
                "cancelled",
                "retry_wait",
            }:
                task.status = "queued"
                task.attempts = 0
                task.retry_at = 0
                task.error = ""
            else:
                raise ValueError("Azione non disponibile nello stato corrente")
        if action == "cancel" and task_id not in self.active:
            shutil.rmtree(self.directory(task_id), ignore_errors=True)

    def transfer(self, task: DownloadTask, partial: Path):
        snapshot = task.snapshot
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > task.total:
            partial.unlink()
            offset = 0
        if offset == task.total:
            return
        headers = {"Accept-Encoding": "identity"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
            if task.etag:
                headers["If-Range"] = task.etag
        with self.http.stream(snapshot["payload"]["url"], headers) as response:
            if response.status_code in {408, 429, 500, 502, 503, 504}:
                value = response.headers.get("retry-after", "0")
                try:
                    delay = (
                        int(value)
                        if value.isdigit()
                        else max(0, int(parsedate_to_datetime(value).timestamp() - time.time()))
                    )
                except (ValueError, TypeError):
                    delay = 0
                raise Retryable(f"Provider HTTP {response.status_code}", delay)
            if response.status_code not in {200, 206}:
                raise ValueError(f"Download rifiutato (HTTP {response.status_code}); controllare la fonte")
            if response.status_code == 206:
                match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("content-range", ""))
                if (
                    not match
                    or int(match[1]) != offset
                    or int(match[3]) != task.total
                    or int(match[2]) != task.total - 1
                ):
                    raise ValueError("Risposta Range non coerente")
                mode = "ab"
            else:
                offset = 0
                mode = "wb"
            self.checkpoint(task.id, offset, etag=response.headers.get("etag", ""))
            with partial.open(mode) as stream:
                last_report = 0.0
                for chunk in response.iter_bytes():
                    offset += len(chunk)
                    if offset > task.total:
                        raise ValueError("Dimensione del download superiore al manifest")
                    stream.write(chunk)
                    if time.monotonic() - last_report >= 0.2:
                        stream.flush()
                        self.checkpoint(task.id, offset)
                        last_report = time.monotonic()
            self.checkpoint(task.id, offset)
        if offset != task.total:
            raise Retryable("Trasferimento incompleto")

    def run(self, task_id):
        folder = self.directory(task_id)
        partial = folder / "download.part"
        try:
            with self.sessions() as db:
                task = db.get(DownloadTask, task_id)
                entry = db.get(DiscoveryEntry, task.entry_id)
                if not entry or not entry.available or not entry.downloadable:
                    raise ValueError("Autorizzazione o disponibilità della fonte cambiata")
            snapshot = task.snapshot
            name = snapshot["payload"]["filename"]
            if not supported_download(snapshot["platform"], name):
                raise ValueError("Nome o formato del file non supportato")
            folder.mkdir(parents=True, exist_ok=True)
            final = folder / name
            if not final.exists():
                self.transfer(task, partial)
            source = final if final.exists() else partial
            self.checkpoint(task_id, status="verifying")
            if source.stat().st_size != task.total:
                raise ValueError("Dimensione inattesa")
            sha256 = digest(source)
            expected = snapshot["payload"].get("expected_sha256")
            blob = snapshot["payload"].get("git_blob_sha1")
            if not expected and not blob:
                raise ValueError("Riferimento di integrità assente")
            if expected and sha256 != expected.lower():
                raise ValueError("SHA-256 non corrispondente")
            if blob:
                sha1 = hashlib.sha1(f"blob {task.total}\0".encode())
                with source.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(65536), b""):
                        sha1.update(chunk)
                if sha1.hexdigest() != blob:
                    raise ValueError("Hash Git della fonte non corrispondente")
            if not final.exists():
                partial.replace(final)
            validate_archive(final)
            self.checkpoint(task_id, status="downloaded", sha256=sha256)
            (folder / "authorization.json").write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            item = candidate([final], folder, snapshot["platform"])
            item.pop("entrypoints")
            cover_path = ""
            cover_error = ""
            if self.cover_loader and snapshot["payload"].get("cover"):
                try:
                    cover_path = str(self.cover_loader(snapshot))
                except Exception as exc:
                    cover_error = f"Copertina non acquisita: {exc}"
                    logger.warning("%s: %s", task_id, cover_error)
            redundant_copy = False
            with self.lock, self.sessions.begin() as db:
                task = db.get(DownloadTask, task_id)
                if task.status in {"paused", "cancelled"} or self.stop.is_set():
                    raise Interrupted()
                game = db.scalar(select(Game).where(Game.sha256 == item["sha256"]))
                if not game:
                    item.update(
                        title=snapshot["title"],
                        author=snapshot.get("author") or "",
                        year=snapshot.get("year"),
                        genre=snapshot.get("genre") or "",
                        description=snapshot.get("description") or "",
                        cover_path=cover_path,
                    )
                    game = Game(
                        **item,
                        license=snapshot["license"],
                        provenance=f"{snapshot['source_url']} | {snapshot['payload']['evidence']['url']}",
                    )
                    db.add(game)
                    db.flush()
                elif Path(game.local_path).is_file() and digest(Path(game.local_path)) == sha256:
                    redundant_copy = Path(game.local_path) != final
                else:
                    for key in ("files", "local_path", "size", "format"):
                        setattr(game, key, item[key])
                task.game_id = game.id
                task.status = "imported"
                task.received = task.total
                task.error = cover_error
                entry = db.get(DiscoveryEntry, task.entry_id)
                if entry:
                    entry.sha256 = sha256
            if redundant_copy:
                final.unlink(missing_ok=True)
            logger.info("Acquired %s SHA-256 %s", task_id, sha256)
        except Interrupted:
            pass
        except (httpx.TransportError, Retryable) as exc:
            with self.lock, self.sessions.begin() as db:
                task = db.get(DownloadTask, task_id)
                if task.status not in {"paused", "cancelled"}:
                    task.status = "retry_wait" if task.attempts < 3 else "failed"
                    task.retry_at = time.time() + max(2**task.attempts, getattr(exc, "delay", 0))
                    task.error = str(exc)
        except Exception as exc:
            logger.exception("Download %s failed", task_id)
            partial.unlink(missing_ok=True)
            with self.lock, self.sessions.begin() as db:
                task = db.get(DownloadTask, task_id)
                if task.status not in {"paused", "cancelled"}:
                    task.status = "failed"
                    task.error = str(exc)
        finally:
            with self.sessions() as db:
                cancelled = db.get(DownloadTask, task_id).status == "cancelled"
            if cancelled:
                shutil.rmtree(folder, ignore_errors=True)
