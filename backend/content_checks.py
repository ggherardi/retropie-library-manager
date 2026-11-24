"""Conservative content checks. These establish a format, never a gameplay claim."""

import hashlib
import re
from pathlib import Path

from backend.config import EXTENSIONS
from backend.paths import reference
from backend.scanner import CUE_FILE, linked_files

# Digests only, no firmware. https://docs.libretro.com/library/pcsx_rearmed/
PSX_BIOS = {
    "scph1001.bin": "924e392ed05558ffdb115408c263dccf",
    "scph5500.bin": "8dd7d5296a650fac7319bce665a6a53c",
    "scph5501.bin": "490f666e1afb15b7362b406ed1cea246",
    "scph5502.bin": "32736f17079d0b2b7024407c39bd3050",
    "scph7001.bin": "1e68c231d0896b7eadcad1d7d8e76129",
    "scph101.bin": "6e3735ff4c7dc899ee98981385f6f3d0",
    "psxonpsp660.bin": "c53ca5908936d412331790f4426c6c33",
}
DOCUMENTS = {
    ".txt",
    ".pdf",
    ".cfg",
    ".xml",
    ".json",
    ".ini",
    ".html",
    ".png",
    ".jpg",
    ".jpeg",
    ".sav",
    ".srm",
    ".state",
    ".dsv",
}


def format_check(path: Path) -> dict:
    """Read at most 128 KiB. Unknown raw formats require a verified catalog hash."""
    size = path.stat().st_size
    with path.open("rb") as stream:
        data = stream.read(131072)
    suffix = path.suffix.lower()
    result = {"platform": "", "basis": "", "kind": "game", "valid": False, "reason": "", "choices": []}
    if size == 524288:
        with path.open("rb") as stream:
            md5 = hashlib.md5(stream.read()).hexdigest()
        if md5 in PSX_BIOS.values():
            return {
                **result,
                "kind": "bios",
                "valid": True,
                "platform": "psx",
                "basis": "MD5 BIOS noto",
                "reason": "BIOS riconosciuto separatamente; nessun trasferimento automatico",
            }
    if re.match(r"(?i)^(scph\d+|psxonpsp|neogeo|uni-bios|sp-s\d|sp-u\d|sfix|sm1)([._-]|$)", path.name):
        return {**result, "kind": "bios", "reason": "Possibile BIOS: hash da verificare nella diagnostica"}
    if suffix in DOCUMENTS or (suffix == ".md" and not data[0x100:0x104] == b"SEGA"):
        return {**result, "kind": "ignored", "reason": "Documento, immagine, configurazione o salvataggio"}
    platform, basis = "", ""
    if suffix == ".tap" and data.startswith(b"C64-TAPE-RAW") and data[12:14] in {b"\x00\x00", b"\x01\x00"}:
        if len(data) < 20 or size <= 20 or int.from_bytes(data[16:20], "little") != size - 20:
            raise ValueError("Immagine nastro C64 incompleta: dimensione diversa dall'intestazione TAP")
        return {
            **result,
            "platform": "c64",
            "kind": "unsupported_platform",
            "basis": "Intestazione e lunghezza del nastro TAP Commodore 64 verificate. Titolo dal nome del file.",
            "reason": "L’importazione sul Raspberry non dispone di un profilo per i nastri Commodore 64.",
        }
    if data.startswith(b"NES\x1a"):
        if len(data) < 16:
            raise ValueError("Header NES troncato")
        required = 16 + (512 if data[6] & 4 else 0) + data[4] * 16384 + data[5] * 8192
        if data[7] & 12 == 8 and data[9]:
            return {
                **result,
                "choices": ["nes"],
                "reason": "Header NES 2.0 con dimensione estesa: richiede hash DAT verificato",
            }
        if not data[4] or size < required:
            raise ValueError("ROM NES troncata: dimensione inferiore ai banchi dichiarati")
        platform, basis = "nes", "Header iNES e dimensioni dei banchi"
    elif (
        len(data) >= 0x150
        and suffix in {".gb", ".gbc", ".bin"}
        and data[0x104:0x108] == bytes.fromhex("ceed6666")
    ):
        checksum = 0
        for byte in data[0x134:0x14D]:
            checksum = (checksum - byte - 1) & 255
        if checksum != data[0x14D]:
            raise ValueError("Checksum header Game Boy errato")
        code = data[0x148]
        required = (
            (32768 << code)
            if code <= 8
            else {0x52: 72 * 16384, 0x53: 80 * 16384, 0x54: 96 * 16384}.get(code, 0)
        )
        if not required or size < required:
            raise ValueError("ROM Game Boy troncata o dimensione header non supportata")
        platform, basis = (
            ("gbc" if data[0x143] in {0x80, 0xC0} else "gb"),
            "Header Game Boy, checksum e dimensione",
        )
    elif suffix == ".gba" and len(data) >= 0xC0 and data[0xB2] == 0x96:
        if (-sum(data[0xA0:0xBD]) - 0x19) & 255 != data[0xBD]:
            raise ValueError("Checksum header GBA errato")
        platform, basis = "gba", "Header e checksum GBA"
    elif data[0x100:0x104] == b"SEGA" and size >= 512:
        platform, basis = "megadrive", "Header SEGA a 0x100"
    elif suffix in {".sms", ".gg", ".bin"}:
        for offset in (0x1FF0, 0x3FF0, 0x7FF0):
            if data[offset : offset + 8] == b"TMR SEGA" and len(data) >= offset + 16:
                region = data[offset + 15] >> 4
                platform = "gamegear" if region in {5, 6, 7} else "mastersystem" if region in {3, 4} else ""
                basis = "Firma TMR SEGA e codice hardware"
                break
    elif suffix in {".sfc", ".smc"}:
        for offset in (0x7FC0, 0xFFC0, 0x81C0, 0x101C0):
            header = data[offset : offset + 64]
            if (
                len(header) == 64
                and int.from_bytes(header[28:30], "little") ^ int.from_bytes(header[30:32], "little") == 65535
                and header[61] >= 0x80
            ):
                platform, basis = "snes", "Header SNES, complemento checksum e vettore reset"
                break
    elif suffix == ".a78" and data[1:10] == b"ATARI7800" and len(data) >= 128:
        if size < 128 + int.from_bytes(data[49:53], "big"):
            raise ValueError("ROM Atari 7800 troncata")
        platform, basis = "atari7800", "Header Atari 7800 e dimensione"
    elif suffix in {".cue", ".m3u", ".iso", ".chd", ".pbp"}:
        platform, basis = "psx", "Struttura disco PS1 (verifica dei riferimenti richiesta)"
    elif suffix in {".zip", ".7z"}:
        return {**result, "kind": "archive", "reason": "Confronto dei membri con i DAT richiesto"}
    if platform:
        return {**result, "valid": True, "platform": platform, "basis": basis}
    choices = [EXTENSIONS[suffix]] if suffix in EXTENSIONS else []
    if suffix == ".bin":
        choices = ["megadrive", "psx"]
    if suffix not in EXTENSIONS and suffix != ".bin":
        return {**result, "kind": "ignored", "reason": "Accessorio o formato non supportato"}
    return {
        **result,
        "choices": choices,
        "reason": "Formato grezzo o header non verificato: serve una corrispondenza hash affidabile",
    }


def disc_check(path: Path, root: Path, seen=None):
    seen = set() if seen is None else seen
    if path in seen:
        raise ValueError("Riferimento disco ciclico")
    seen = seen | {path}
    suffix = path.suffix.lower()
    if suffix == ".m3u":
        files = linked_files(path, root)
        for file in files[1:]:
            if file.suffix.lower() in {".cue", ".iso", ".chd", ".pbp"}:
                disc_check(file, root, seen)
        return
    if suffix == ".cue":
        linked_files(path, root)
        current = None
        sector_size = 0
        data_tracks = 0
        track = False
        indexed = False
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = CUE_FILE.match(line)
            if match:
                current = reference(path.parent, match.group(1) or match.group(2), root)
            elif re.match(r"\s*TRACK\s", line, re.I):
                if track and not indexed:
                    raise ValueError("Traccia CUE priva di INDEX 01")
                mode = line.split()[-1].upper()
                if current is None or mode not in {"MODE2/2352", "MODE1/2352", "MODE1/2048", "AUDIO"}:
                    raise ValueError("Traccia CUE non supportata o FILE assente")
                sector_size = 2048 if mode == "MODE1/2048" else 2352
                if not current.stat().st_size or current.stat().st_size % sector_size:
                    raise ValueError(f"BIN troncato/non allineato: {current.name}")
                if mode != "AUDIO":
                    iso_check(
                        current,
                        sector_size,
                        24 if mode == "MODE2/2352" else 16 if mode == "MODE1/2352" else 0,
                    )
                    data_tracks += 1
                track, indexed = True, False
            else:
                index = re.match(r"\s*INDEX\s+(\d+)\s+(\d+):(\d+):(\d+)\s*$", line, re.I)
                if index:
                    number, minutes, seconds, frames = map(int, index.groups())
                    if (
                        not track
                        or current is None
                        or seconds >= 60
                        or frames >= 75
                        or (minutes * 60 * 75 + seconds * 75 + frames) * sector_size >= current.stat().st_size
                    ):
                        raise ValueError("Indice CUE fuori dal file BIN")
                    indexed |= number == 1
        if not data_tracks or not indexed:
            raise ValueError("CUE senza traccia dati PS1 completa")
    elif suffix == ".iso":
        iso_check(path, 2048, 0)
    elif suffix == ".chd":
        with path.open("rb") as stream:
            head = stream.read(124)
        if (
            head[:8] != b"MComprHD"
            or len(head) < 108
            or int.from_bytes(head[12:16], "big") not in {4, 5}
            or int.from_bytes(head[8:12], "big") not in {108, 124}
        ):
            raise ValueError("Header CHD non valido/non supportato")
        # Container integrity needs chdman, performed by identification when available.
    elif suffix == ".pbp":
        with path.open("rb") as stream:
            head = stream.read(40)
            if head[:4] != b"\x00PBP" or len(head) != 40:
                raise ValueError("Header PBP non valido")
            stream.seek(int.from_bytes(head[36:40], "little"))
            if stream.read(12) not in {b"PSISOIMG0000", b"PSTITLEIMG00"}:
                raise ValueError("PBP non identificato come disco PS1")


def iso_check(path, sector_size, offset):
    size = path.stat().st_size
    if size % sector_size or size < 17 * sector_size:
        raise ValueError("Immagine disco troncata")
    with path.open("rb") as stream:
        stream.seek(16 * sector_size + offset)
        pvd = stream.read(2048)
        if pvd[:7] != b"\x01CD001\x01" or b"PLAYSTATION" not in pvd[8:72]:
            raise ValueError("Disco non identificato come PlayStation (descrittore ISO9660)")
        sectors = int.from_bytes(pvd[80:84], "little")
        if sectors != int.from_bytes(pvd[84:88], "big") or sectors * sector_size > size:
            raise ValueError("Dimensione ISO9660 incoerente: immagine incompleta")
