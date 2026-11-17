"""Two individually reviewed releases; no blanket authorization for a collection."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

CURATED: list[dict[str, Any]] = [
    {
        "id": "miniplanets",
        "title": "Miniplanets REMIX",
        "platform": "megadrive",
        "author": "Javier Degirolmo (Sik)",
        "year": 2022,
        "license": "Zlib",
        "repo": "sikthehedgehog/miniplanets",
        "revision": "0ac9c395289cc5d0837c96d45e61a27300e8eebc",
        "file": "Miniplanets REMIX Ver (REV04).bin",
        "rights_repo": "sikthehedgehog/miniplanets",
        "rights_revision": "0ac9c395289cc5d0837c96d45e61a27300e8eebc",
        "rights_file": "LICENSE.txt",
        "rights_blob": "04f63819dbf4c8bb8437ba714b9e08b1c541c893",
        "required_text": ["Permission is granted to anyone", "redistribute it"],
        "assets_license": "Zlib",
    },
    {
        "id": "horizontal-shooter",
        "title": "Horizontal Shooter",
        "platform": "snes",
        "author": "Marcus Rowe (UnDisbeliever)",
        "year": 2016,
        "license": "MIT",
        "repo": "retrobrews/snes-games",
        "revision": "2329cb432b4cad13aa6a9d2ad0699c771780b378",
        "file": "horizontal-shooter.sfc",
        "rights_repo": "retrobrews/snes-games",
        "rights_revision": "2329cb432b4cad13aa6a9d2ad0699c771780b378",
        "rights_file": "horizontal-shooter.txt",
        "rights_blob": None,
        "required_text": [
            "This code is licensed under the MIT license.",
            "licensed under CC-0.",
            "https://github.com/undisbeliever/horizontal-shooter",
        ],
        "assets_license": "CC0-1.0",
        "original_url": "https://github.com/undisbeliever/horizontal-shooter",
    },
]


def load_curated(http, cache, progress):
    result = []
    for index, item in enumerate(CURATED):
        tree = json.loads(
            http.read(
                f"https://api.github.com/repos/{item['repo']}/git/trees/{item['revision']}?recursive=1",
                3_000_000,
            )
        )
        nodes = {n["path"]: n for n in tree["tree"] if n["type"] == "blob"}
        node = nodes.get(item["file"])
        rights = nodes.get(item["rights_file"])
        if not node or not rights:
            raise ValueError("File o prova di autorizzazione non disponibile: " + item["id"])
        url = f"https://raw.githubusercontent.com/{item['rights_repo']}/{item['rights_revision']}/{quote(item['rights_file'], safe='/')}"
        cached = cache / (rights["sha"] + ".rights")
        content = cached.read_bytes() if cached.exists() else http.read(url, 100000)
        actual = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
        if actual != rights["sha"] or (item["rights_blob"] and actual != item["rights_blob"]):
            raise ValueError("Dichiarazione di licenza modificata")
        declaration = content.decode("utf-8-sig")
        if any(phrase not in declaration for phrase in item["required_text"]):
            raise ValueError("Autorizzazione specifica non verificata")
        cached.write_bytes(content)
        result.append(
            {
                "id": hashlib.sha256(("curated-homebrew:" + item["id"]).encode()).hexdigest(),
                "provider_id": "curated-homebrew",
                "external_id": item["id"],
                "title": item["title"],
                "platform": item["platform"],
                "author": item["author"],
                "year": item["year"],
                "genre": "Shooter" if item["id"] == "horizontal-shooter" else "Platform",
                "description": "Homebrew con autorizzazione verificata per questo specifico file.",
                "license": item["license"],
                "source_url": item.get("original_url", f"https://github.com/{item['repo']}"),
                "size": node["size"],
                "available": True,
                "downloadable": True,
                "reason": "",
                "sha256": None,
                "payload": {
                    "url": f"https://raw.githubusercontent.com/{item['repo']}/{item['revision']}/{quote(item['file'])}",
                    "filename": item["file"],
                    "git_blob_sha1": node["sha"],
                    "expected_sha256": None,
                    "cover": None,
                    "evidence": {
                        "url": url,
                        "revision": item["revision"],
                        "license": item["license"],
                        "assets_license": item["assets_license"],
                        "declaration": declaration,
                        "rights_blob": actual,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "basis": "Singolo titolo revisionato; download dal file originale fissato a revisione Git",
                    },
                },
            }
        )
        progress(index + 1, len(CURATED))
    return result
