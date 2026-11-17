"""Bounded streaming readers. Catalogs describe content and never authorize downloads."""

import csv
import hashlib
import json
import re
import shlex
from pathlib import PurePosixPath
from typing import Any

import ijson
from defusedxml import ElementTree as XML

from backend.config import PLATFORMS

MAX_COMPONENTS = 10000


def member_name(value):
    value = str(value)
    path = PurePosixPath(value.replace("\\", "/"))
    if (
        not value
        or len(value) > 500
        or path.is_absolute()
        or ".." in path.parts
        or ":" in value
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("Nome componente non sicuro")
    return path.as_posix()


def text(value, limit=500):
    value = str(value or "").strip()
    if len(value) > limit or any(ord(c) < 32 and c not in "\n\t\r" for c in value):
        raise ValueError("Campo catalogo troppo lungo o non valido")
    return value


def components(values):
    if len(values) > MAX_COMPONENTS:
        raise ValueError("Troppi componenti nel ROM set")
    result = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("Componente non strutturato")
        size = value.get("size")
        size = (
            int(str(size), 16 if str(size).lower().startswith("0x") else 10)
            if size not in [None, ""]
            else None
        )
        if size is not None and not 0 <= size <= 8 * 1024**3:
            raise ValueError("Dimensione componente non valida")
        item = {
            "name": member_name(value.get("name", "")),
            "size": size,
            "merge": member_name(value["merge"]) if value.get("merge") else "",
            "status": text(value.get("status") or value.get("flags") or "good", 50),
            "optional": str(value.get("optional", "no")).lower() in {"yes", "true", "1"},
            "bios": text(value.get("bios"), 100),
            "kind": value.get("kind", "rom"),
        }
        for key, length in [("crc", 8), ("sha1", 40), ("sha256", 64), ("md5", 32)]:
            val = str(value.get(key) or "").lower()
            if val and not re.fullmatch("[0-9a-f]{" + str(length) + "}", val):
                raise ValueError("Hash DAT non valido: " + key)
            item[key] = val
        result.append(item)
    return result


def normalize(raw, platform):
    name = text(raw.get("name") or raw.get("id") or raw.get("title"), 300)
    if not name:
        raise ValueError("Nome del ROM set mancante")
    platform = text(raw.get("platform") or platform, 30)
    if platform not in PLATFORMS:
        raise ValueError("Piattaforma catalogo non supportata")
    parent = text(raw.get("cloneof") or raw.get("parent"), 300)
    romof = text(raw.get("romof"), 300)
    system = text(raw.get("system"), 100)
    if (
        romof == "neogeo"
        or name == "neogeo"
        or "neogeo" in str(raw.get("sourcefile", "")).lower()
        or system.lower() in {"neogeo", "neo geo", "mvs", "aes"}
    ):
        system = "Neo Geo"
        platform = "neogeo"
    elif not system:
        source = str(raw.get("sourcefile", "")).lower()
        system = next(
            (
                label
                for key, label in [("cps1", "CPS-1"), ("cps2", "CPS-2"), ("cps3", "CPS-3")]
                if key in source
            ),
            "Arcade" if platform in {"arcade", "fba", "mame-libretro"} else PLATFORMS[platform],
        )
    players = raw.get("players")
    players = int(players) if str(players).isdigit() else None
    if players is not None and not 0 <= players <= 64:
        raise ValueError("Numero di giocatori non valido")
    parts = raw.get("components", raw.get("roms", []))
    if isinstance(parts, str):
        parts = json.loads(parts or "[]")
    kind = (
        "bios"
        if str(raw.get("isbios", "")).lower() == "yes" or raw.get("runnable") == "no"
        else "device"
        if str(raw.get("isdevice", "")).lower() == "yes"
        else raw.get("kind", "game")
    )
    if kind not in {"game", "bios", "device"}:
        raise ValueError("Tipo record non valido")
    deps = raw.get("dependencies", [])
    if isinstance(deps, str):
        deps = [s.strip() for s in deps.split("|") if s.strip()]
    result = {
        "name": name,
        "title": text(raw.get("description") or raw.get("title") or name),
        "platform": platform,
        "system": system,
        "manufacturer": text(raw.get("manufacturer"), 300),
        "year": text(raw.get("year"), 20),
        "genre": text(raw.get("genre"), 120),
        "players": players,
        "orientation": text(raw.get("orientation") or raw.get("rotate"), 30),
        "controls": text(raw.get("controls"), 300),
        "parent": parent,
        "family": parent or name,
        "romof": romof,
        "kind": kind,
        "components": components(parts),
        "details": {
            "dependencies": [text(d, 300) for d in deps],
            "declared_status": text(raw.get("driver_status") or raw.get("status") or "unknown", 100),
            "description": text(raw.get("synopsis"), 20000),
            "mode": text(raw.get("mode") or "unknown", 20),
            "sourcefile": text(raw.get("sourcefile"), 500),
        },
    }
    result["payload_sha"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return result


def xml_records(stream, header):
    depth = 0
    root = None
    nodes = 0
    for event, node in XML.iterparse(
        stream, events=("start", "end"), forbid_dtd=False, forbid_entities=True, forbid_external=True
    ):
        if event == "start":
            depth += 1
            nodes += 1
            if root is None:
                root = node
                header.update(node.attrib)
            if depth > 64 or nodes > 100000:
                raise ValueError("Record XML troppo complesso")
            continue
        assert root is not None
        if depth == 2 and node.tag == "header":
            header.update({child.tag: child.text or "" for child in node})
            root.remove(node)
            nodes = 0
        elif depth == 2 and node.tag in {"game", "machine", "software"}:
            raw = dict(node.attrib)
            for key in ["description", "year", "manufacturer"]:
                raw[key] = node.findtext(key) or ""
            raw["components"] = [{**r.attrib, "kind": r.tag} for r in node if r.tag in {"rom", "disk"}]
            raw["dependencies"] = [r.get("name") for r in node.findall("device_ref") if r.get("name")]
            display = node.find("display")
            video = node.find("video")
            if display is not None:
                raw["rotate"] = display.get("rotate", "")
            elif video is not None:
                raw["orientation"] = video.get("orientation", "")
            inputs = node.find("input")
            if inputs is not None:
                raw["players"] = inputs.get("players")
                raw["controls"] = "; ".join(
                    filter(None, [inputs.get("control")] + [c.get("type") for c in inputs.findall("control")])
                )
            driver = node.find("driver")
            if driver is not None:
                raw["driver_status"] = driver.get("status")
            yield raw
            root.remove(node)
            node.clear()
            nodes = 0
        depth -= 1


def cmp_records(stream, header):
    lexer = shlex.shlex(stream, posix=True, punctuation_chars="()")
    lexer.whitespace_split = True
    lexer.commenters = "#;"
    lexer.escape = ""
    pending: list[str] = []

    def token():
        value = pending.pop(0) if pending else lexer.get_token()
        if value and len(value) > 1 and set(value) <= set("()"):
            pending.extend(value[1:])
            value = value[0]
        if value is not None and len(value) > 20000:
            raise ValueError("Token DAT troppo lungo")
        return value

    def block(depth=0):
        if depth > 12:
            raise ValueError("DAT troppo annidato")
        result: dict[str, list[Any]] = {}
        count = 0
        while True:
            key = token()
            if key == ")":
                return result
            if key is None:
                raise ValueError("DAT interrotto")
            value = token()
            if value == "(":
                value = block(depth + 1)
            elif value is None or value == ")":
                raise ValueError("Coppia DAT non valida")
            key = key.lower()
            count += 1
            if count > 20000:
                raise ValueError("Record DAT troppo grande")
            result.setdefault(key, []).append(value)

    while True:
        section = token()
        if section is None:
            return
        if token() != "(":
            raise ValueError("Formato ClrMamePro non valido")
        values = block()
        if section.lower() in {"clrmamepro", "header"}:
            header.update({k: v[0] for k, v in values.items() if isinstance(v[0], str)})
        elif section.lower() in {"game", "machine", "resource"}:
            raw: dict[str, Any] = {k: v[0] for k, v in values.items() if isinstance(v[0], str)}
            raw["components"] = [
                {**{k: v[0] for k, v in r.items()}, "kind": kind}
                for kind in ["rom", "disk"]
                for r in values.get(kind, [])
                if isinstance(r, dict)
            ]
            if section.lower() == "resource":
                raw["kind"] = "bios"
            yield raw


def records(path, format_name, platform, header, hints=None):
    if path.stat().st_size > 512 * 1024**2:
        raise ValueError("Catalogo oltre il limite di 512 MiB")
    if format_name == "auto":
        with path.open("rb") as stream:
            prefix = stream.read(256).lstrip(b"\xef\xbb\xbf \n\r\t")
        format_name = (
            "xml"
            if prefix.startswith(b"<")
            else "json"
            if prefix.startswith(b"[")
            else "csv"
            if path.suffix.lower() == ".csv"
            else "dat"
        )
    with path.open(
        "rb" if format_name in {"xml", "json"} else "r",
        **({} if format_name in {"xml", "json"} else {"encoding": "utf-8-sig", "newline": ""}),
    ) as stream:
        if format_name == "xml":
            rows = xml_records(stream, header)
        elif format_name == "dat":
            rows = cmp_records(stream, header)
        elif format_name == "json":
            rows = ijson.items(stream, "item")
        elif format_name == "csv":
            csv.field_size_limit(2_000_000)
            rows = csv.DictReader(stream)
        else:
            raise ValueError("Formato catalogo non supportato")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Record catalogo non strutturato")
            if hints and row.get("name") in hints:
                row = {**hints[row["name"]], **{k: v for k, v in row.items() if v not in [None, ""]}}
            yield normalize(row, platform)
