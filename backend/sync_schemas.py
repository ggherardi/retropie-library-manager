import re
from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, field_validator

from backend.schemas import Input


def remote_path(value):
    path = PurePosixPath(value)
    if (
        not path.is_absolute()
        or len(path.parts) < 3
        or ".." in path.parts
        or "\\" in value
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("Usare una directory remota assoluta e specifica, senza traversal")
    return str(path)


class DeviceInput(Input):
    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(default="pi", pattern=r"^[a-z_][a-z0-9_-]{0,31}$")
    rom_root: str = "/home/pi/RetroPie/roms"
    bios_root: str = "/home/pi/RetroPie/BIOS"
    safety_bytes: int = Field(default=1_000_000_000, ge=64 * 1024**2, le=1_000_000_000_000)
    chd_confirmed: bool = False
    is_default: bool = False

    @field_validator("host")
    @classmethod
    def valid_host(cls, value):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]*", value):
            raise ValueError("Hostname o indirizzo IP non valido")
        return value

    @field_validator("rom_root", "bios_root")
    @classmethod
    def valid_root(cls, value):
        return remote_path(value)


class TrustInput(Input):
    fingerprint: str = Field(pattern=r"^SHA256:[A-Za-z0-9+/]{43}$")
    confirmed: Literal[True]


class SyncInput(Input):
    device_id: str
    game_ids: list[int] = Field(min_length=1, max_length=20000)
    metadata: bool = True
    covers: bool = False
    screenshots: bool = False
    collection: bool = False
    collection_partial: bool = False


class SyncConfirm(Input):
    confirmed: Literal[True]
    rights_confirmed: Literal[True]
    media_rights_confirmed: bool = False


class SyncControl(Input):
    action: Literal["cancel", "retry", "pause", "resume"]
