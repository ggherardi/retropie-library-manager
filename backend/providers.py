import ipaddress
import socket
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from backend.config import EXTENSIONS
from backend.paths import digest
from backend.schemas import DownloadEntry, ProviderInput


class Provider(Protocol):
    def catalog(self) -> list[DownloadEntry]: ...


class ManifestProvider:
    def __init__(self, manifest: ProviderInput):
        self.manifest = manifest

    def catalog(self) -> list[DownloadEntry]:
        return self.manifest.entries


def validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise ValueError("Il provider deve usare un URL HTTPS pubblico senza credenziali")
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Indirizzo del provider non pubblico")


def download(entry: DownloadEntry, directory: Path, transport=None) -> Path:
    validate_url(entry.url)
    validate_url(entry.rights_url)
    extension = Path(entry.filename).suffix.lower()
    if EXTENSIONS.get(extension) != entry.platform and not (
        extension == ".zip" and entry.platform in {"arcade", "neogeo"}
    ):
        raise ValueError("Formato del download non supportato per questa console")
    directory.mkdir(parents=True, exist_ok=True)
    final = directory / f"{entry.sha256.lower()}-{entry.filename}"
    if final.exists():
        if digest(final) == entry.sha256.lower() and final.stat().st_size == entry.size:
            return final
        raise ValueError("Un download esistente ha un hash inatteso")
    partial = directory / f"{uuid4()}.part"
    try:
        with httpx.Client(timeout=60, follow_redirects=False, trust_env=False, transport=transport) as client:
            with client.stream("GET", entry.url) as response:
                if response.status_code != 200:
                    raise ValueError(
                        f"Download rifiutato dal provider (HTTP {response.status_code}). Usare l'URL HTTPS finale."
                    )
                size = 0
                with partial.open("xb") as stream:
                    for chunk in response.iter_bytes(1024 * 1024):
                        size += len(chunk)
                        if size > entry.size:
                            raise ValueError("Dimensione superiore a quella dichiarata")
                        stream.write(chunk)
        if partial.stat().st_size != entry.size or digest(partial) != entry.sha256.lower():
            raise ValueError("Verifica SHA-256 o dimensione fallita")
        partial.replace(final)
        return final
    finally:
        partial.unlink(missing_ok=True)
