"""Content hashes from bounded ZIP/7z streams; no archive paths are extracted to disk."""

import hashlib
import stat
import threading
import zipfile
import zlib

import py7zr

from backend.catalog_formats import member_name

MAX_BYTES = 2 * 1024**3
MAX_MEMBERS = 20000


class DigestSink(py7zr.Py7zIO):
    def __init__(self, budget, checkpoint):
        self.count = 0
        self.crc = 0
        self.sha1 = hashlib.sha1()
        self.sha256 = hashlib.sha256()
        self.md5 = hashlib.md5()
        self.budget = budget
        self.checkpoint = checkpoint

    def write(self, data):
        with self.budget["lock"]:
            self.budget["bytes"] += len(data)
            if self.budget["bytes"] > MAX_BYTES:
                raise ValueError("Archivio espanso troppo grande")
        self.count += len(data)
        self.crc = zlib.crc32(data, self.crc)
        for sha in [self.sha1, self.sha256, self.md5]:
            sha.update(data)
        self.checkpoint()
        return len(data)

    def read(self, size=None):
        return b""

    def seek(self, offset, whence=0):
        return offset

    def flush(self):
        pass

    def size(self):
        return self.count

    def result(self):
        return {
            "size": self.count,
            "crc": f"{self.crc & 0xFFFFFFFF:08x}",
            "sha1": self.sha1.hexdigest(),
            "sha256": self.sha256.hexdigest(),
            "md5": self.md5.hexdigest(),
        }


class DigestFactory(py7zr.WriterFactory):
    def __init__(self, expected, checkpoint):
        self.expected = expected
        self.checkpoint = checkpoint
        self.products = {}
        self.budget = {"bytes": 0, "lock": threading.Lock()}

    def create(self, filename):
        name = member_name(filename)
        if name not in self.expected or name in self.products:
            raise ValueError("Membro archivio inatteso o duplicato")
        product = DigestSink(self.budget, self.checkpoint)
        self.products[name] = product
        return product


def inspect_archive(path, checkpoint=lambda: None):
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Archivio troppo grande")
    result = {}
    total = 0
    names = set()

    def check(name, size):
        nonlocal total
        name = member_name(name)
        if name.casefold() in names:
            raise ValueError("Nomi duplicati o ambigui nell’archivio")
        names.add(name.casefold())
        total += size
        if len(names) > MAX_MEMBERS or total > MAX_BYTES:
            raise ValueError("Archivio espanso troppo grande")
        checkpoint()
        return name

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            if len(archive.infolist()) > MAX_MEMBERS:
                raise ValueError("Troppi membri ZIP")
            for entry in archive.infolist():
                name = check(entry.filename, entry.file_size)
                mode = entry.external_attr >> 16
                if (
                    stat.S_ISLNK(mode)
                    or (stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)))
                    or entry.flag_bits & 1
                ):
                    raise ValueError("Archivio con link, file speciali o cifratura")
                if entry.file_size > max(entry.compress_size, 1) * 1000:
                    raise ValueError("Rapporto di compressione non sicuro")
                if entry.is_dir():
                    continue
                sink = DigestSink({"bytes": 0, "lock": threading.Lock()}, checkpoint)
                with archive.open(entry) as stream:
                    for chunk in iter(lambda: stream.read(65536), b""):
                        sink.write(chunk)
                result[name] = sink.result()
                if result[name]["size"] != entry.file_size:
                    raise ValueError("Dimensione ZIP non corrispondente")
    elif path.suffix.lower() == ".7z":
        with py7zr.SevenZipFile(path, "r") as archive:
            if archive.needs_password():
                raise ValueError("Archivio 7z cifrato")
            expected = {}
            for item in archive.files:
                if item.is_symlink or item.is_junction or item.is_socket:
                    raise ValueError("Link o file speciale nel 7z")
                name = check(item.filename, item.uncompressed)
                if not item.is_directory:
                    expected[name] = item.uncompressed
            if total > max(path.stat().st_size, 1) * 1000:
                raise ValueError("Rapporto di compressione non sicuro")
            factory = DigestFactory(expected, checkpoint)
            archive.extractall(factory=factory)
            result = {name: product.result() for name, product in factory.products.items()}
            if set(result) != set(expected) or any(result[n]["size"] != s for n, s in expected.items()):
                raise ValueError("Contenuto 7z incompleto")
    else:
        raise ValueError("La validazione arcade richiede ZIP o 7z")
    return result


def matches(expected, actual):
    hashes = [key for key in ["sha256", "sha1", "md5", "crc"] if expected.get(key)]
    return bool(
        hashes
        and expected.get("size") is not None
        and actual
        and actual["size"] == expected["size"]
        and all(actual.get(key) == expected[key] for key in hashes)
    )


def validate_set(entry, catalog, archives, mode, checkpoint=lambda: None):
    """archives maps technical set name to path; caches only hashes, not decompressed bytes."""
    cache = {}
    used = {}
    problems = []
    checks = []
    bios = []
    visiting = set()
    visited = set()

    def inventory(name):
        if name not in archives:
            return None
        if name not in cache:
            path = archives[name]
            before = path.stat()
            sha = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(262144), b""):
                    sha.update(block)
                    checkpoint()
            cache[name] = inspect_archive(path, checkpoint)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError("Archivio modificato durante la validazione")
            used[name] = {"path": str(path), "size": before.st_size, "sha256": sha.hexdigest()}
        return cache[name]

    main_name = entry["parent"] if mode == "merged" and entry["parent"] else entry["name"]

    def visit(record, role="game"):
        name = record["name"]
        if name in visiting:
            raise ValueError("Dipendenze DAT cicliche")
        if name in visited:
            return
        visiting.add(name)
        for part in record["components"]:
            if part["optional"]:
                continue
            if (
                part["kind"] != "rom"
                or part["status"] == "nodump"
                or part["size"] is None
                or not any(part.get(k) for k in ["crc", "sha1", "sha256", "md5"])
            ):
                problems.append(
                    {
                        "set": name,
                        "file": part["name"],
                        "reason": "Componente non verificabile (CHD/nodump/hash o dimensione assente)",
                    }
                )
                continue
            candidates = []
            if role == "bios":
                if mode == "full-non-merged":
                    candidates = [(main_name, part["name"])]
                else:
                    candidates = [(name, part["name"])]
            elif mode == "merged":
                candidates = [
                    (main_name, name + "/" + part["name"]),
                    (main_name, part.get("merge") or part["name"]),
                    (main_name, part["name"]),
                ]
            elif mode == "split" and part.get("merge"):
                owners = [record["parent"], record["romof"]]
                for owner in list(owners):
                    ancestor = catalog.get(owner, {})
                    owners.extend([ancestor.get("parent", ""), ancestor.get("romof", "")])
                candidates = [(owner, part["merge"]) for owner in dict.fromkeys(owners) if owner]
            else:
                candidates = [(main_name if role == "game" else name, part["name"])]
            found = None
            for set_name, file_name in candidates:
                contents = inventory(set_name)
                if contents is not None and matches(part, contents.get(file_name)):
                    found = {"archive": set_name, "member": file_name}
                    break
            checks.append(
                {"set": name, "file": part["name"], "matched": found, "expected": part, "role": role}
            )
            if not found:
                problems.append(
                    {
                        "set": name,
                        "file": part["name"],
                        "reason": "Componente mancante o nome/dimensione/hash differente",
                    }
                )
        dependencies = list(record["details"].get("dependencies", []))
        if record["romof"] and record["romof"] != record["parent"]:
            dependencies.append(record["romof"])
        if record["parent"] and mode in {"split", "merged"}:
            dependencies.append(record["parent"])
        for dep in dict.fromkeys(dependencies):
            target = catalog.get(dep)
            if target is None:
                problems.append({"set": dep, "file": "", "reason": "Dipendenza assente dal DAT"})
                continue
            is_bios = target["kind"] == "bios"
            if is_bios:
                bios.append(dep)
            visit(target, "bios" if is_bios else "parent")
        visiting.remove(name)
        visited.add(name)

    visit(entry, "bios" if entry["kind"] == "bios" else "game")
    if not checks:
        problems.append({"set": entry["name"], "file": "", "reason": "Nessun componente ROM verificabile"})
    status = "complete" if not problems else "incomplete"
    return {
        "status": status,
        "set_name": entry["name"],
        "mode": mode,
        "main_archive": main_name,
        "checks": checks,
        "problems": problems,
        "bios": list(dict.fromkeys(bios)),
        "archives": used,
        "launchable": status == "complete"
        and entry["kind"] == "game"
        and not (mode == "merged" and entry["parent"]),
        "launch_note": "Un clone merged richiede una selezione del set nel core: esportazione automatica bloccata"
        if mode == "merged" and entry["parent"]
        else "",
        "compatibility": "not_assessed",
        "tested": False,
    }
