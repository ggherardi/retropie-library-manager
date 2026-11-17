import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import quote, urlsplit

from backend.config import EXTENSIONS
from backend.network import PublicHTTP

SOURCES = {
    "gbdev": {"name": "GBDev · Homebrew Hub", "repo": "gbdev/database"},
    "gbadev": {"name": "GBADev · Homebrew Hub", "repo": "gbadev-org/games"},
    "nesdev": {"name": "NESDev · Homebrew Hub", "repo": "nesdev-org/homebrew-db"},
}
LINK_SOURCES = [
    {
        "id": "itch",
        "name": "itch.io",
        "url": "https://itch.io/games/tag-homebrew",
        "status": "link_only",
        "message": "API autenticate e percorsi di download esclusi da robots.txt. Usare la pagina dell'autore.",
        "evidence": "https://itch.io/docs/api/serverside",
    },
    {
        "id": "pdroms",
        "name": "PDRoms",
        "url": "https://pdroms.de/",
        "status": "link_only",
        "message": "Autorizzazione all'automazione non verificata; controllo TLS di robots.txt fallito durante l'integrazione. Collegamento originale disponibile.",
        "evidence": "https://pdroms.de/robots.txt",
    },
]
LICENSES = {
    "MIT",
    "Zlib",
    "ISC",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "Apache-2.0",
    "Unlicense",
    "CC0-1.0",
    "GPL-2.0",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "CC-BY-3.0",
    "CC-BY-4.0",
    "CC-BY-SA-3.0",
    "CC-BY-SA-4.0",
    "CC-BY-NC-4.0",
    "CC-BY-NC-SA-4.0",
    "CC-BY-NC-ND-4.0",
    "CC-BY-ND-4.0",
}
GENRES = {
    "Arcade",
    "RPG",
    "Adventure",
    "Action",
    "Puzzle",
    "Platform",
    "Survival",
    "Shooter",
    "Visual Novel",
    "Simulation",
    "Educational",
    "Rhythm",
    "Card Game",
    "Strategy",
    "Racing",
    "Sports",
    "Fighting",
}


def identity(provider: str, slug: str) -> str:
    return hashlib.sha256(f"{provider}:{slug}".encode()).hexdigest()


def public_link(value) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("url")
    if isinstance(value, str) and urlsplit(value).scheme in {"http", "https"}:
        return value
    return None


def author_name(value) -> str | None:
    if isinstance(value, list):
        return ", ".join(filter(None, (author_name(v) for v in value))) or None
    if isinstance(value, dict):
        value = value.get("name")
    return value.strip()[:500] if isinstance(value, str) and value.strip() else None


def safe_filename(name: str) -> bool:
    return bool(
        name
        and not PureWindowsPath(name).is_reserved()
        and PurePosixPath(name).name == name
        and "\\" not in name
        and ":" not in name
        and name not in {".", ".."}
        and not name.endswith((".", " "))
    )


def supported_download(platform: str, filename: str) -> bool:
    extension = PurePosixPath(filename).suffix.lower()
    if extension == ".cue":
        return False  # A single remote descriptor cannot supply the linked tracks.
    return safe_filename(filename) and (
        EXTENSIONS.get(extension) == platform
        or (extension == ".zip" and platform in {"arcade", "neogeo"})
        or (extension == ".bin" and platform == "megadrive")
    )


def parse_entry(provider: str, revision: str, path: str, raw: dict, tree: dict) -> dict | None:
    if raw.get("typetag") not in {"game", "homebrew"}:
        return None
    repo = SOURCES[provider]["repo"]
    slug = raw.get("slug") or PurePosixPath(path).parent.name
    metadata_url = f"https://raw.githubusercontent.com/{repo}/{revision}/{quote(path, safe='/')}"
    folder = str(PurePosixPath(path).parent)
    license_name = raw.get("gameLicense") or raw.get("license") or None
    assets_license = raw.get("assetsLicense") or raw.get("assetLicense") or None
    platform = str(raw.get("platform", "")).lower()
    files = [f for f in raw.get("files", []) if f.get("type", "rom") == "rom" and f.get("playable", True)]
    preferred = [f for f in files if f.get("default")]
    selected = preferred[0] if len(preferred) == 1 else files[0] if len(files) == 1 else {}
    filename = selected.get("filename", "")
    node = tree.get(f"{folder}/{filename}", {}) if safe_filename(filename) else {}
    disabled = raw.get("use-requirements", {}).get("disable-downloads", False) or selected.get(
        "use-requirements", {}
    ).get("disable-downloads", False)
    permitted = license_name in LICENSES and (assets_license is None or assets_license in LICENSES)
    supported = EXTENSIONS.get(PurePosixPath(filename).suffix.lower()) == platform and platform in {
        "nes",
        "gb",
        "gbc",
        "gba",
    }
    reason = ""
    if disabled or raw.get("commercial"):
        reason = "Download disabilitato dalla fonte o titolo commerciale"
    elif not permitted:
        reason = "Licenza assente, non verificata o condizioni degli asset non compatibili"
    elif not selected:
        reason = "Scelta del file ambigua: consultare la fonte"
    elif not supported or not node.get("size"):
        reason = "File o formato non disponibile/supportato"
    screenshot = next(
        (s for s in raw.get("screenshots", []) if isinstance(s, str) and safe_filename(s)), None
    )
    cover_node = tree.get(f"{folder}/{screenshot}", {}) if screenshot else {}
    cover = None
    if screenshot and assets_license in LICENSES and cover_node.get("size", 0) <= 8_000_000:
        cover = {
            "url": f"https://raw.githubusercontent.com/{repo}/{revision}/{quote(folder + '/' + screenshot, safe='/')}",
            "git_blob_sha1": cover_node.get("sha"),
            "license": assets_license,
        }
    date = str(raw.get("date", ""))
    year = int(date[:4]) if re.match(r"^\d{4}(?:-|$)", date) else None
    sha256 = selected.get("hash", {}).get("sha256")
    if sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
        sha256 = None
    return {
        "id": identity(provider, str(slug)),
        "provider_id": provider,
        "external_id": str(slug),
        "title": (raw.get("title") or str(slug))[:300],
        "platform": platform or "unknown",
        "author": author_name(raw.get("developer")),
        "year": year,
        "genre": next((tag for tag in raw.get("tags", []) if tag in GENRES), None),
        "description": raw.get("description") or None,
        "license": license_name,
        "source_url": public_link(raw.get("website") or raw.get("gameWebsite"))
        or public_link(raw.get("repository"))
        or f"https://github.com/{repo}/tree/{revision}/{quote(folder, safe='/')}",
        "size": node.get("size"),
        "available": bool(node),
        "downloadable": not reason,
        "reason": reason,
        "sha256": sha256.lower() if sha256 else None,
        "payload": {
            "url": f"https://raw.githubusercontent.com/{repo}/{revision}/{quote(folder + '/' + filename, safe='/')}"
            if node
            else None,
            "filename": filename,
            "git_blob_sha1": node.get("sha"),
            "expected_sha256": sha256,
            "cover": cover,
            "evidence": {
                "url": metadata_url,
                "revision": revision,
                "license": license_name,
                "assets_license": assets_license,
                "download_disabled": disabled,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "declaration": raw,
            },
        },
    }


class GitHubCatalog:
    """Read only metadata blobs. ROM content is fetched by the confirmed queue."""

    def __init__(self, http: PublicHTTP, cache: Path):
        self.http = http
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)

    def load(self, provider: str, progress=lambda done, total: None) -> list[dict]:
        repo = SOURCES[provider]["repo"]
        tree = json.loads(
            self.http.read(f"https://api.github.com/repos/{repo}/git/trees/HEAD?recursive=1", 20_000_000)
        )
        if tree.get("truncated"):
            raise ValueError("Inventario GitHub troncato: aggiornamento annullato")
        nodes = {n["path"]: n for n in tree["tree"] if n["type"] == "blob"}
        metadata = [n for p, n in nodes.items() if p.startswith("entries/") and p.endswith("/game.json")]
        revision = tree["sha"]

        def parse(node):
            cached = self.cache / f"{node['sha']}.json"
            if cached.exists():
                content = cached.read_bytes()
            else:
                url = f"https://raw.githubusercontent.com/{repo}/{revision}/{quote(node['path'], safe='/')}"
                content = self.http.read(url, 1_000_000)
                actual = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
                if actual != node["sha"]:
                    raise ValueError("Hash dei metadati GitHub non valido")
                cached.write_bytes(content)
            return parse_entry(provider, revision, node["path"], json.loads(content), nodes)

        result = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            for index, item in enumerate(pool.map(parse, metadata), 1):
                if item:
                    result.append(item)
                if index % 20 == 0 or index == len(metadata):
                    progress(index, len(metadata))
        logging.getLogger("rlm").info("Catalog %s loaded %d games", provider, len(result))
        return result
