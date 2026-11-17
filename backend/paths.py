import hashlib
from pathlib import Path


def local_path(value: str, must_exist: bool = True) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute() or value.startswith(("\\\\", "//")) or ".." in path.parts:
        raise ValueError("Usare un percorso locale assoluto senza '..' o condivisioni di rete")
    if ":" in str(path)[2:]:
        raise ValueError("Percorso non valido")
    return path.resolve(strict=must_exist)


def within(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve(strict=True)):
        raise ValueError("Il percorso esce dalla cartella autorizzata")
    return resolved


def allowed(value: str, roots: list[str]) -> Path:
    path = local_path(value)
    if not any(path.is_relative_to(local_path(root, must_exist=False)) for root in roots):
        raise ValueError("Aggiungere prima la cartella alle sorgenti nelle Impostazioni")
    return path


def digest(path: Path, checkpoint=lambda: None) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checkpoint()
            sha.update(chunk)
    return sha.hexdigest()


def reference(parent: Path, name: str, root: Path) -> Path:
    normalized = name.replace("\\", "/")
    relative = Path(normalized)
    if relative.is_absolute() or ".." in relative.parts or ":" in normalized:
        raise ValueError("Riferimento CUE/M3U non sicuro")
    return within(parent / relative, root)
