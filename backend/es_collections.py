"""RetroPie EmulationStation custom collections, verified against the installed binary."""

import hashlib
import posixpath
import re
import xml.etree.ElementTree as ET

from backend.gamelist import parse_xml
from backend.remote_fs import rpc

NAME = "Grandi Classici"


def parse_settings(content):
    # Settings.cpp saves siblings directly under an XML document, without a <config> root.
    text = content.decode("utf-8-sig")
    declaration = re.match(r"\s*(<\?xml[^?]*\?>)", text)
    header = declaration.group(0) if declaration else ""
    body = text[len(header) :]
    root = parse_xml(("<rlm-settings>" + body + "</rlm-settings>").encode())
    if any(
        isinstance(node.tag, str) and node.tag not in {"bool", "int", "float", "string", "map"}
        for node in root
    ):
        raise ValueError("Formato impostazioni EmulationStation non supportato")
    return root, header


def serialize_settings(root, header):
    return (
        header + (root.text or "") + "".join(ET.tostring(node, encoding="unicode") for node in root)
    ).encode("utf-8")


SUPPORT = r"""
import pathlib,json,hashlib
binary=pathlib.Path('/opt/retropie/supplementary/emulationstation/emulationstation')
data=binary.read_bytes() if binary.is_file() else b''
markers=[b'/.emulationstation/collections',b'/custom-',b'CollectionSystemsCustom',b'custom-.cfg']
print(json.dumps({'supported':all(m in data for m in markers),'binary_sha256':hashlib.sha256(data).hexdigest() if data else None,'format':'custom-<name>.cfg, one absolute ROM path per line','evidence':'https://github.com/RetroPie/EmulationStation/blob/d9efd746a983a382d9fe031b5336317455dd0d4d/es-app/src/CollectionSystemManager.cpp'}))
"""


def build_collection_files(connection, remote, config, diag, manifest, games, encode):
    support = rpc(connection, SUPPORT)
    if not support.get("supported"):
        return (
            [],
            support,
            [
                "Raccolte personalizzate non verificate su questo EmulationStation: raccolta disponibile in Windows."
            ],
        )
    by_id = {game.id: game for game in games}
    members = [entry for entry in manifest["games"] if getattr(by_id[entry["id"]], "_rlm_classic", False)]
    members.sort(
        key=lambda entry: (getattr(by_id[entry["id"]], "_rlm_position", 0), entry["title"].casefold())
    )
    paths = [posixpath.join(config["rom_root"], entry["launch"]) for entry in members]
    if any("\n" in p or "\r" in p or not p.startswith(config["rom_root"] + "/") for p in paths):
        raise ValueError("Percorso raccolta non valido")
    collection_path = diag["es_root"] + "/collections/custom-" + NAME + ".cfg"
    old = remote.read(collection_path)
    # Preserve user-added entries. Remove only obsolete references in our managed groups.
    foreign = []
    managed_paths = {posixpath.join(config["rom_root"], entry["launch"]) for entry in manifest["games"]}
    for line in (old or b"").decode("utf-8-sig").splitlines():
        if line and line not in managed_paths:
            foreign.append(line)
    paths = list(dict.fromkeys(paths + foreign))
    content = ("\n".join(paths) + ("\n" if paths else "")).encode()
    settings_path = diag["es_root"] + "/es_settings.cfg"
    settings = remote.read(settings_path)
    if settings is None:
        return [], support, ["Impostazioni EmulationStation assenti: attivare la raccolta dal menu locale."]
    root, header = parse_settings(settings)
    nodes = [n for n in root.findall("string") if n.get("name") == "CollectionSystemsCustom"]
    if len(nodes) > 1:
        raise ValueError("Impostazione raccolte duplicata: revisione richiesta")
    node = (
        nodes[0] if nodes else ET.SubElement(root, "string", {"name": "CollectionSystemsCustom", "value": ""})
    )
    names = [v for v in node.get("value", "").split(",") if v]
    updated_settings = settings
    # An empty collection stays available in Windows and is not enabled as a fake installed system.
    if paths and NAME not in names:
        node.set("value", ",".join(names + [NAME]))
        updated_settings = serialize_settings(root, header)
    files = []
    for path, previous, value, kind in [
        (collection_path, old, content, "collection"),
        (settings_path, settings, updated_settings, "es_settings"),
    ]:
        item = encode(path, value, kind)
        sha = hashlib.sha256(previous).hexdigest() if previous is not None else None
        item.update(
            read_path=path if previous is not None else None,
            original_sha=sha,
            original_target_sha=sha,
            state="present" if previous == value else "update",
            backup_bytes=len(previous or b""),
            references=[],
        )
        files.append(item)
    support.update(
        members=len(members), retained_external_entries=len(foreign), name=NAME, enabled=bool(paths)
    )
    return files, support, []
