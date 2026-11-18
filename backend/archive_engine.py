"""7-Zip is an installed decoder, never an archive-supplied executable.

Only stdout is extracted: the decoder cannot choose filesystem destinations.
All calls run inside the resource-limited archive worker and its Job Object.
"""

import functools
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

from backend.archive_volumes import source_parts

MIN_VERSION = (26, 6)


def command(args, sink=None, limit=32 * 1024**2):
    process = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    stdout, stderr = process.stdout, process.stderr
    assert stdout is not None and stderr is not None
    errors = bytearray()
    output = bytearray()

    def drain():
        for data in iter(lambda: stderr.read(4096), b""):
            if len(errors) + len(data) > 65536:
                process.kill()
                break
            errors.extend(data)

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        for data in iter(lambda: stdout.read(65536), b""):
            if sink:
                sink.write(data)
            else:
                if len(output) + len(data) > limit:
                    raise ValueError("Risposta del decoder oltre il limite")
                output.extend(data)
        code = process.wait()
        reader.join(timeout=5)
        if code:
            text = errors.decode("utf-8", "replace") + output.decode("utf-8", "replace")
            if "password" in text.lower() or "encrypted archive" in text.lower():
                raise ValueError(
                    "Archivio protetto da password: usare una copia non cifrata ottenuta dalla fonte autorizzata"
                )
            if (
                "missing volume" in text.lower()
                or "unexpected end" in text.lower()
                or "Split After = +" in text
            ):
                raise ValueError(
                    "Archivio incompleto: volume mancante o troncato. Aggiungere tutti i volumi e rianalizzare. "
                    + text[-800:]
                )
            if "unsupported" in text.lower():
                raise ValueError("Metodo di compressione non supportato dal motore 7-Zip. " + text[-800:])
            raise ValueError("Archivio corrotto o decodifica non riuscita. " + text[-800:])
        return bytes(output)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        reader.join(timeout=5)
        stdout.close()
        stderr.close()


@functools.lru_cache(maxsize=1)
def engine():
    configured = os.environ.get("RLM_7ZIP", "")
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            raise ValueError("RLM_7ZIP deve indicare un eseguibile installato con percorso assoluto")
    elif os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "7-Zip" / "7z.exe"
    else:
        candidate = Path(shutil.which("7zz") or "/usr/bin/7zz")
    if not candidate.is_file():
        raise ValueError("Motore 7-Zip assente: eseguire Setup.cmd per installarlo, poi Rianalizza")
    version = command([str(candidate), "i"], limit=1024**2).decode("utf-8", "replace")
    match = re.search(r"7-Zip[^\r\n]*?\b(\d+)\.(\d+)\b", version)
    if not match or tuple(map(int, match.groups())) < MIN_VERSION:
        raise ValueError("Serve 7-Zip 26.06 o successivo: eseguire Setup.cmd e rianalizzare")
    return str(candidate)


def args(path, operation):
    first, _, kind, _ = source_parts(path)
    if kind == "rar":
        with first.open("rb") as stream:
            signature = stream.read(8)
        if signature.startswith(b"Rar!\x1a\x07\x00"):
            kind = "Rar"
        elif signature == b"Rar!\x1a\x07\x01\x00":
            kind = "Rar5"
        else:
            raise ValueError("Firma RAR non valida; archivi autoestraenti non supportati")
    return [
        engine(),
        operation,
        "-t" + kind,
        "-sccUTF-8",
        "-bd",
        "-y",
        "-pRLM-PASSWORDS-NOT-SUPPORTED",
        "-mmt1",
    ], first


def inventory(path):
    base, first = args(path, "l")
    text = command([*base, "-slt", "-ba", "--", str(first)]).decode("utf-8", "strict")
    result = []
    for block in re.split(r"\r?\n\r?\n", text.strip("\r\n")):
        fields = {}
        for line in block.splitlines():
            key, sep, value = line.partition(" = ")
            if not sep or key in fields:
                raise ValueError("Metadati archivio ambigui o non supportati")
            fields[key] = value
        if not {"Path", "Size", "Folder"}.issubset(fields) or fields["Folder"] not in {"+", "-"}:
            raise ValueError("Elenco membri incompleto o non supportato")
        attributes = fields.get("Attributes", "").split()
        if fields.get("Encrypted") == "+":
            raise ValueError("Archivio protetto da password: cifratura non supportata")
        if any(
            fields.get(k, "") not in {"", "-"}
            for k in ("Symbolic Link", "Hard Link", "Copy Link", "Reparse", "Alternate Stream")
        ) or any(len(a) >= 10 and a[0] not in {"-", "d"} for a in attributes):
            raise ValueError("Archivio con link o file speciali non supportato")
        result.append(
            {"name": fields["Path"], "size": int(fields["Size"]), "directory": fields["Folder"] == "+"}
        )
    return result


def extract(path, entries, factory):
    # Test the entire set first, including last-volume markers, solid streams and CRCs.
    base, first = args(path, "t")
    command([*base, "-bso0", "--", str(first)])
    base, first = args(path, "x")
    for member in entries:
        if member["directory"]:
            continue
        sink = factory.create(member["name"])
        # Literal include avoids interpreting a member beginning with @ as a host-side list file.
        command([*base, "-so", "-spd", "-i!" + member["name"], "--", str(first)], sink)
