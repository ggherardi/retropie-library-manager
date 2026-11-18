"""Bounded archive preparation. Originals and published library sources are immutable."""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

import py7zr

from backend.paths import digest
from backend.scanner import CUE_FILE

ARCHIVES = {".zip", ".7z"}
MAX_MEMBERS = 20000
MAX_FILE = 8 * 1024**3
MAX_TOTAL = 16 * 1024**3
MAX_DEPTH = 3
MAX_RATIO = 1000
MAX_SECONDS = 900
RESERVE = 1024**3
VERSION = 1


def safe_name(value):
    value = str(value).replace("\\", "/")
    path = PurePosixPath(value)
    if (
        not value
        or len(value) > 500
        or path.is_absolute()
        or not path.parts
        or any(
            p in {".", ".."}
            or p.endswith((".", " "))
            or re.search(r'[<>:"|?*\x00-\x1f]', p)
            or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", p)
            for p in value.rstrip("/").split("/")
        )
    ):
        raise ValueError(f"Percorso archivio non sicuro: {value[:150]}")
    return path.as_posix()


def check_7z_resources(archive):
    streams = archive.header.main_streams
    if not streams or not streams.unpackinfo:
        return
    for folder in streams.unpackinfo.folders:
        for coder in folder.coders:
            properties = coder.get("properties") or b""
            method = coder["method"]
            memory = 0
            if method == bytes.fromhex("030101") and len(properties) >= 5:
                memory = int.from_bytes(properties[1:5], "little")
            elif method == bytes.fromhex("21") and properties:
                prop = properties[0]
                memory = (2 | (prop & 1)) << (prop // 2 + 11) if prop < 40 else 2**32
            elif method == bytes.fromhex("030401") and len(properties) >= 5:
                memory = int.from_bytes(properties[1:5], "little")
            if memory > 64 * 1024**2:
                raise ValueError("7z: dizionario di decompressione oltre il limite di 64 MiB")


def normalize_descriptors(root, names):
    lookup = {name.casefold(): name for name in names}
    changed = []
    for name in names:
        path = root / name
        if path.suffix.lower() not in {".cue", ".m3u"}:
            continue
        if path.stat().st_size > 1024**2:
            raise ValueError("Descrittore CUE/M3U oltre il limite di 1 MiB")
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeError:
            continue  # The identifier will report this descriptor independently.
        lines = []
        for line in text.splitlines(keepends=True):
            match = CUE_FILE.match(line.rstrip("\r\n")) if path.suffix.lower() == ".cue" else None
            ref = (
                (match.group(1) or match.group(2))
                if match
                else line.strip()
                if path.suffix.lower() == ".m3u" and line.strip() and not line.lstrip().startswith("#")
                else ""
            )
            if ref:
                normalized = safe_name(ref)
                key = (PurePosixPath(name).parent / normalized).as_posix().casefold()
                if key in lookup:
                    actual = PurePosixPath(lookup[key]).relative_to(PurePosixPath(name).parent).as_posix()
                    if ref != actual:
                        line = line.replace(ref, actual, 1)
            lines.append(line)
        updated = "".join(lines).encode("utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf8")
        if updated != raw:
            path.write_bytes(updated)
            changed.append(name)
    return changed


def _inventory(path, checkpoint=lambda: None):
    """Metadata inspection does not extract members or trust their names as identity."""
    if path.stat().st_size > MAX_FILE:
        raise ValueError("Archivio oltre il limite di 8 GiB")
    result = []
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for entry in archive.infolist():
                mode = entry.external_attr >> 16
                if (
                    stat.S_ISLNK(mode)
                    or (stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)))
                    or entry.flag_bits & 1
                ):
                    raise ValueError("ZIP con link, file speciali o cifratura non supportato")
                if entry.file_size > max(1, entry.compress_size) * MAX_RATIO:
                    raise ValueError("ZIP bomb: rapporto di compressione oltre il limite")
                result.append(
                    {"name": safe_name(entry.filename), "size": entry.file_size, "directory": entry.is_dir()}
                )
                checkpoint()
    elif path.suffix.lower() == ".7z":
        with py7zr.SevenZipFile(path, "r", max_extract_size=MAX_TOTAL) as archive:
            check_7z_resources(archive)
            if archive.needs_password():
                raise ValueError("Archivio 7z cifrato: formato non supportato")
            for entry in archive.files:
                if entry.is_symlink or entry.is_junction or entry.is_socket:
                    raise ValueError("7z con link o file speciali non supportato")
                result.append(
                    {
                        "name": safe_name(entry.filename),
                        "size": entry.uncompressed or 0,
                        "directory": entry.is_directory,
                    }
                )
                checkpoint()
    else:
        raise ValueError("Formato archivio non supportato: usare ZIP o 7z")
    if len(result) > MAX_MEMBERS or sum(e["size"] for e in result) > MAX_TOTAL:
        raise ValueError("Archivio oltre il limite di membri o dimensione espansa")
    if sum(e["size"] for e in result) > max(1, path.stat().st_size) * MAX_RATIO:
        raise ValueError("Archivio bomb: rapporto di compressione oltre il limite")
    names = {}
    for member in result:
        name = member["name"].casefold()
        if name in names or member["size"] < 0 or member["size"] > MAX_FILE:
            raise ValueError("Membri duplicati, dimensioni eccessive o non valide")
        names[name] = member
    for name in names:
        if any(
            str(p) in names and not names[str(p)]["directory"]
            for p in PurePosixPath(name).parents
            if str(p) != "."
        ):
            raise ValueError("Conflitto file/cartella nell'archivio")
    return result


def run_worker(request, checkpoint, work=None):
    request["limits"] = {
        name: globals()[name]
        for name in (
            "MAX_MEMBERS",
            "MAX_FILE",
            "MAX_TOTAL",
            "MAX_DEPTH",
            "MAX_RATIO",
            "MAX_SECONDS",
            "RESERVE",
        )
    }
    request["parent_pid"] = os.getpid()
    with tempfile.TemporaryDirectory(prefix="work-", dir=work) as directory:
        job = Path(directory).resolve()
        if work and not job.is_relative_to(work.resolve()):
            raise ValueError("Worker fuori dallo staging autorizzato")
        (job / "request.json").write_text(json.dumps(request), encoding="utf8")
        process = subprocess.Popen(
            [sys.executable, "-m", "backend.archive_worker", str(job)],
            cwd=Path(__file__).resolve().parent.parent,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        def release():
            return None

        try:
            if os.name == "nt":
                from backend.archive_worker import windows_job

                release = windows_job(process.pid)
            (job / "go").touch()
            deadline = time.monotonic() + MAX_SECONDS
            while process.poll() is None:
                checkpoint()
                if time.monotonic() > deadline:
                    raise ValueError("Preparazione interrotta: limite di tempo superato")
                time.sleep(0.05)
            output = job / "result.json"
            if not output.is_file() or output.stat().st_size > 32 * 1024**2:
                raise ValueError("Decoder arrestato: limite di memoria/CPU o archivio non valido")
            value = json.loads(output.read_text(encoding="utf8"))
            if value.get("error") or process.returncode:
                raise ValueError("Analisi archivio: " + value.get("error", "decoder non riuscito"))
            return value["output"]
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            release()


def inventory(path, checkpoint=lambda: None):
    return run_worker({"operation": "inventory", "path": str(path)}, checkpoint)


class Budget:
    def __init__(self, checkpoint):
        self.checkpoint = checkpoint
        self.bytes = 0
        self.members = 0
        self.started = time.monotonic()
        self.lock = threading.Lock()

    def check(self, count=0):
        with self.lock:
            self.bytes += count
            if self.bytes > MAX_TOTAL or time.monotonic() - self.started > MAX_SECONDS:
                raise ValueError("Limite di dimensione o tempo della preparazione superato")
        self.checkpoint()

    def reserve(self, entries, depth):
        self.check()
        self.members += len(entries)
        if depth > MAX_DEPTH or self.members > MAX_MEMBERS:
            raise ValueError("Limite di profondità o membri degli archivi annidati superato")
        if self.bytes + sum(e["size"] for e in entries) > MAX_TOTAL:
            raise ValueError("Dimensione cumulativa degli archivi annidati oltre il limite")


class FileSink(py7zr.Py7zIO):
    def __init__(self, path, expected, budget):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = path.open("xb")
        self.expected, self.budget, self.count = expected, budget, 0
        self.sha = hashlib.sha256()

    def write(self, data):
        self.budget.check(len(data))
        if self.count + len(data) > self.expected:
            raise ValueError("Dimensione estratta superiore a quella dichiarata")
        self.stream.write(data)
        self.sha.update(data)
        self.count += len(data)
        return len(data)

    def read(self, size=None):
        return b""

    def seek(self, offset, whence=0):
        if whence != 0 or offset not in {0, self.count}:
            raise ValueError("Scrittura archivio non sequenziale")
        return offset

    def flush(self):
        if not self.stream.closed:
            self.stream.flush()

    def size(self):
        return self.count

    def close(self):
        if not self.stream.closed:
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.stream.close()


class FileFactory(py7zr.WriterFactory):
    def __init__(self, root, expected, budget):
        self.root, self.expected, self.budget = root, expected, budget
        self.products = {}

    def create(self, filename):
        name = safe_name(filename)
        if name not in self.expected or name in self.products:
            raise ValueError("Membro archivio inatteso o duplicato")
        target = self.root / name
        if not target.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Membro fuori dalla cartella di preparazione")
        sink = FileSink(target, self.expected[name], self.budget)
        self.products[name] = sink
        return sink

    def close(self):
        for sink in self.products.values():
            sink.close()


class ArchiveStore:
    def __init__(self, data):
        self.root = (data / "prepared-archives").resolve()
        if not self.root.is_relative_to(data.resolve()):
            raise ValueError("Directory di preparazione fuori dai dati dell’applicazione")
        self.work = self.root / ".staging"

    def clean(self, path):
        # Delete only our transient extraction directories, never published sources.
        resolved = path.resolve()
        if (
            path.is_symlink()
            or not resolved.is_relative_to(self.work.resolve())
            or resolved == self.work.resolve()
            or not path.name.startswith("work-")
        ):
            raise ValueError("Cleanup fuori dallo staging autorizzato")
        shutil.rmtree(resolved)

    def recover(self):
        self.work.mkdir(parents=True, exist_ok=True)
        for path in self.work.glob("work-*"):
            if path.is_dir():
                self.clean(path)

    def prepare(self, path, entries, budget, depth=0):
        self.work.mkdir(parents=True, exist_ok=True)
        previous_bytes, previous_members = budget.bytes, budget.members
        budget.reserve(entries, depth)
        # Charge the full declared output even if CRC fails or a nested decoder aborts.
        budget.bytes += sum(entry["size"] for entry in entries)
        result = run_worker(
            {
                "operation": "prepare",
                "path": str(path),
                "data": str(self.root.parent),
                "entries": entries,
                "depth": depth,
                "bytes": previous_bytes,
                "members": previous_members,
            },
            budget.check,
            self.work,
        )
        budget.bytes, budget.members = result["bytes"], result["members"]
        budget.check()
        return Path(result["prepared"]), result["report"]

    def _prepare(self, path, entries, budget, depth=0, staging=None):
        budget.reserve(entries, depth)
        initial = path.stat()
        sha = digest(path, budget.check)
        folder = self.root / f"v{VERSION}-{sha}"
        if folder.is_symlink() or not folder.resolve().is_relative_to(self.root):
            raise ValueError("Cache archivio fuori dalla directory autorizzata")
        manifest_path = folder / "manifest.json"
        if manifest_path.is_file():
            report = json.loads(manifest_path.read_text(encoding="utf8"))
            if report.get("archive_sha256") != sha or report.get("version") != VERSION:
                raise ValueError("Manifest della preparazione non valido")
            expected = {e["name"]: e["size"] for e in entries if not e["directory"]}
            if set(expected) != set(report["files"]):
                raise ValueError("Manifest della preparazione incompleto")
            for name, info in report["files"].items():
                target = folder / "files" / safe_name(name)
                if not target.resolve().is_relative_to((folder / "files").resolve()):
                    raise ValueError("Sorgente preparata fuori dall'archivio locale")
                if (
                    target.is_symlink()
                    or target.stat().st_size != info["size"]
                    or digest(target, budget.check) != info["sha256"]
                ):
                    raise ValueError("Sorgente preparata modificata: conservata senza sovrascrittura")
            budget.bytes += sum(e["size"] for e in entries)
            budget.check()
            return folder / "files", report
        self.work.mkdir(parents=True, exist_ok=True)
        total = sum(e["size"] for e in entries)
        if total + RESERVE > shutil.disk_usage(self.work).free:
            raise ValueError("Spazio PC insufficiente per preparare l'archivio e mantenere 1 GiB libero")
        staging = staging or self.work / ("work-" + str(uuid4()))
        files = staging / "files"
        files.mkdir(parents=True)
        expected = {e["name"]: e["size"] for e in entries if not e["directory"]}
        factory = FileFactory(files, expected, budget)
        try:
            try:
                if path.suffix.lower() == ".zip":
                    with zipfile.ZipFile(path) as archive:
                        for entry in archive.infolist():
                            if entry.is_dir():
                                continue
                            sink = factory.create(entry.filename)
                            with archive.open(entry) as stream:
                                for block in iter(lambda: stream.read(65536), b""):
                                    sink.write(block)
                            sink.close()
                else:
                    with py7zr.SevenZipFile(path, "r", max_extract_size=total) as archive:
                        archive.extractall(factory=factory)
            finally:
                factory.close()
            if set(factory.products) != set(expected) or any(
                sink.count != expected[name] for name, sink in factory.products.items()
            ):
                raise ValueError("Archivio incompleto: dimensioni dei membri non corrispondenti")
            final = path.stat()
            if (initial.st_size, initial.st_mtime_ns) != (final.st_size, final.st_mtime_ns) or digest(
                path, budget.check
            ) != sha:
                raise ValueError("Archivio originale cambiato durante la preparazione")
            normalized = normalize_descriptors(files, expected)
            report = {
                "normalized_descriptors": normalized,
                "version": VERSION,
                "archive_sha256": sha,
                "compressed_bytes": initial.st_size,
                "expanded_bytes": total,
                "members": len(entries),
                "files": {
                    name: {"size": sink.count, "sha256": sink.sha.hexdigest()}
                    for name, sink in factory.products.items()
                },
            }
            for name in normalized:
                report["files"][name] = {
                    "size": (files / name).stat().st_size,
                    "sha256": digest(files / name, budget.check),
                }
            (staging / "manifest.json").write_text(json.dumps(report), encoding="utf8")
            staging.rename(folder)
            return folder / "files", report
        finally:
            if staging.exists():
                self.clean(staging)
