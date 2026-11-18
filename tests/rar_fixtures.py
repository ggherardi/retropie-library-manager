"""Independent stored-only test containers; no RAR compression implementation.

RAR5 layout: https://www.rarlab.com/technote.htm
Compressed/solid/volume cases use ISC-licensed upstream text fixtures instead.
"""

import base64
import hashlib
import json
import struct
import zlib
from pathlib import Path


def vint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    return bytes(result) + bytes([value])


def block5(body):
    raw = vint(len(body)) + body
    return struct.pack("<I", zlib.crc32(raw)) + raw


def block4(body):
    return struct.pack("<H", zlib.crc32(body) & 65535) + body


def rar(path, files, version=5):
    if version == 5:
        chunks = [b"Rar!\x1a\x07\x01\x00", block5(b"\x01\x00\x00")]
        for name, data in files.items():
            encoded = name.encode("utf8")
            body = b"\x02\x02" + vint(len(data)) + b"\x04" + vint(len(data)) + b"\x20"
            body += struct.pack("<I", zlib.crc32(data)) + b"\x00\x00" + vint(len(encoded)) + encoded
            chunks.extend([block5(body), data])
        chunks.append(block5(b"\x05\x00\x00"))
    else:
        chunks = [b"Rar!\x1a\x07\x00", block4(struct.pack("<BHHHI", 0x73, 0, 13, 0, 0))]
        for name, data in files.items():
            encoded = name.encode("ascii")
            body = (
                struct.pack(
                    "<BHHIIBIIBBHI",
                    0x74,
                    0x8000,
                    32 + len(encoded),
                    len(data),
                    len(data),
                    2,
                    zlib.crc32(data),
                    0,
                    20,
                    0x30,
                    len(encoded),
                    0x20,
                )
                + encoded
            )
            chunks.extend([block4(body), data])
        chunks.append(block4(struct.pack("<BHH", 0x7B, 0, 7)))
    path.write_bytes(b"".join(chunks))
    return path


def upstream(folder, names):
    samples = json.loads((Path(__file__).parent / "fixtures/rar-samples.json").read_text(encoding="utf8"))[
        "files"
    ]
    result = []
    for name in names:
        sample = samples[name]
        raw = zlib.decompress(base64.b64decode(sample["zlib_base64"]))
        assert hashlib.sha256(raw).hexdigest() == sample["sha256"]
        path = folder / name
        path.write_bytes(raw)
        result.append(path)
    return result


def split_zip(folder, name, payload):
    import io
    import zipfile

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as target:
        target.writestr("Game.nes", payload)
    raw = bytearray(b"PK\x07\x08" + stream.getvalue())
    central = raw.index(b"PK\x01\x02")
    end = raw.index(b"PK\x05\x06")
    boundary = len(raw) // 2
    struct.pack_into("<I", raw, central + 42, 4)
    struct.pack_into("<HH", raw, end + 4, 1, 1)
    struct.pack_into("<I", raw, end + 16, central - boundary)
    first, final = folder / (name + ".z01"), folder / (name + ".zip")
    first.write_bytes(raw[:boundary])
    final.write_bytes(raw[boundary:])
    return first, final
