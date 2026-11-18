"""Resolve only same-directory volume families; never follow archive-provided paths."""

import io
import re
from contextlib import contextmanager
from pathlib import Path

ARCHIVES = {".zip", ".rar", ".7z"}


def is_archive(path):
    return path.suffix.lower() in ARCHIVES or bool(
        re.search(r"(?i)(?:\.(?:7z|zip)\.\d{3,}|\.[rz]\d{2,})$", path.name)
    )


def source_parts(path):
    path = Path(path).absolute()
    name = path.name
    numbered = re.fullmatch(r"(?i)(.+\.(7z|zip))\.(\d{3,})", name)
    rar = re.fullmatch(r"(?i)(.+)\.part(\d+)\.rar", name)
    legacy = re.fullmatch(r"(?i)(.+)\.([rz])(\d{2,})", name)
    siblings = {}
    for index, child in enumerate(path.parent.iterdir()):
        if index >= 20000:
            raise ValueError("Troppi file nella cartella dei volumi")
        if child.name.casefold() in siblings:
            raise ValueError("Nomi ambigui nella cartella dei volumi")
        siblings[child.name.casefold()] = child

    def member(value):
        item = siblings.get(value.casefold())
        if item is None:
            raise ValueError(
                f"Volume mancante: {value}. Aggiungere tutti i volumi nella stessa selezione/cartella e rianalizzare."
            )
        if item.is_symlink() or item.resolve().parent != path.parent.resolve() or not item.is_file():
            raise ValueError("Volume non regolare o fuori dalla cartella autorizzata: " + value)
        return item

    if numbered or rar:
        match = numbered or rar
        assert match is not None
        stem, width = match[1], len(match[3] if numbered else match[2])
        pattern = re.compile(re.escape(stem) + (r"\.(\d+)" if numbered else r"\.part(\d+)\.rar"), re.I)
        indices = [int(m[1]) for s in siblings if (m := pattern.fullmatch(s))]
        if not indices or max(indices) > 1000 or min(indices) < 1:
            raise ValueError("Numerazione o numero dei volumi non supportato (massimo 1000)")

        def filename(index):
            return f"{stem}.{index:0{width}d}" if numbered else f"{stem}.part{index:0{width}d}.rar"

        parts = [member(filename(i)) for i in range(1, max(indices) + 1)]
        return parts[0], parts, numbered[2].lower() if numbered else "rar", bool(numbered)

    stem = legacy[1] if legacy else path.stem
    family = legacy[2].lower() if legacy else "r" if path.suffix.lower() == ".rar" else "z"
    extension = ".rar" if family == "r" else ".zip"
    pattern = re.compile(re.escape(stem) + rf"\.{family}(\d{{2,}})", re.I)
    indices = [int(m[1]) for s in siblings if (m := pattern.fullmatch(s))]
    if (legacy or path.suffix.lower() in {".rar", ".zip"}) and indices:
        if max(indices) > 999:
            raise ValueError("Troppi volumi (massimo 1000)")
        first = member(stem + extension)
        parts = [
            member(f"{stem}.{family}{i:02d}") for i in range(0 if family == "r" else 1, max(indices) + 1)
        ]
        return first, [first, *parts] if family == "r" else [*parts, first], extension[1:], False
    return member(name), [member(name)], path.suffix.lower()[1:], False


class JoinedReader(io.RawIOBase):
    """Seekable view of byte-split ZIP/7z, without allocating a joined copy."""

    def __init__(self, parts):
        self.parts = parts
        self.sizes = [p.stat().st_size for p in parts]
        self.length, self.position = sum(self.sizes), 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset + (self.position if whence == 1 else self.length if whence == 2 else 0)
        if position < 0:
            raise ValueError("Offset di volume non valido")
        self.position = position
        return position

    def read(self, size=-1):
        remaining = max(0, self.length - self.position)
        size = remaining if size is None or size < 0 else min(size, remaining)
        blocks = []
        offset = 0
        for path, length in zip(self.parts, self.sizes, strict=True):
            if size and offset + length > self.position:
                start = self.position - offset
                count = min(size, length - start)
                with path.open("rb") as stream:
                    stream.seek(start)
                    data = stream.read(count)
                if len(data) != count:
                    raise ValueError("Volume troncato durante la lettura: " + path.name)
                blocks.append(data)
                self.position += count
                size -= count
            offset += length
        return b"".join(blocks)


@contextmanager
def archive_input(path):
    first, parts, kind, joined = source_parts(path)
    if joined:
        with JoinedReader(parts) as stream:
            yield stream
    else:
        yield first


def external(path):
    _, parts, kind, joined = source_parts(path)
    return kind == "rar" or (kind == "zip" and len(parts) > 1 and not joined)
