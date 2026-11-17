from typing import Literal

from pydantic import Field, field_validator

from backend.config import PLATFORMS
from backend.schemas import Input


class CatalogImport(Input):
    source_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    name: str = Field(min_length=1, max_length=300)
    path: str = Field(min_length=1, max_length=4096)
    format: Literal["auto", "xml", "dat", "json", "csv"] = "auto"
    platform: str = "arcade"
    core: Literal["", "lr-mame2003", "lr-fbneo"] = ""
    version: str = Field(default="", max_length=300)
    source_url: str = Field(default="", max_length=2000)
    revision: str = Field(default="", max_length=64, pattern=r"^[a-fA-F0-9]*$")

    @field_validator("platform")
    @classmethod
    def valid_platform(cls, value):
        if value not in PLATFORMS:
            raise ValueError("Piattaforma non supportata")
        return value


class CatalogFilters(Input):
    q: str = Field(default="", max_length=300)
    source_id: str = ""
    platform: str = ""
    system: str = ""
    genre: str = ""
    collection: Literal[
        "all",
        "arcade",
        "neogeo",
        "multiplayer",
        "favorites",
        "tested",
        "missing",
        "unsynced",
        "owned",
        "preferred",
    ] = "all"
    parents_only: bool = False
    kind: Literal["", "game", "bios", "device"] = "game"


class ValidateInput(Input):
    source_id: str
    game_ids: list[int] = Field(min_length=1, max_length=20000)
    mode: Literal["split", "merged", "non-merged", "full-non-merged"] = "split"
    entry_uid: str = ""


class InsightInput(Input):
    preferred_core: Literal["", "lr-mame2003", "lr-fbneo"] = ""
    machine_mode: Literal["unknown", "MVS", "AES"] = "unknown"
    test_status: Literal["untested", "passed", "failed"] = "untested"
    device_id: str = ""
    evidence: str = Field(default="", max_length=4000)
    screenshot_path: str = Field(default="", max_length=4096)
    media_rights_confirmed: bool = False
    confirmed: Literal[True]


class BindCore(Input):
    device_id: str
    source_id: str
    core: Literal["lr-mame2003", "lr-fbneo"]
    evidence: str = Field(min_length=12, max_length=4000)
    confirmed: Literal[True]


class PreferredInput(Input):
    uid: str = Field(min_length=64, max_length=64)


class CorePreference(Input):
    device_id: str
    platform: str
    core: Literal["lr-mame2003", "lr-fbneo"]
    confirmed: Literal[True]


class CatalogMatch(Input):
    source_id: str
    game_ids: list[int] = Field(min_length=1, max_length=20000)
    apply: bool = False


class OfficialCatalog(Input):
    provider: Literal["mame2003", "fbneo-installed", "fbneo-current"]
    device_id: str = ""
