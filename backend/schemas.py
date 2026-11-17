from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.config import PLATFORMS


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SettingsInput(Input):
    import_roots: list[str] = Field(default_factory=list, max_length=30)
    export_root: str = ""


class ScanInput(Input):
    root: str = Field(min_length=1, max_length=4096)
    platform: str | None = None

    @field_validator("platform")
    @classmethod
    def platform_valid(cls, value):
        if value is not None and value not in PLATFORMS:
            raise ValueError("Console non supportata")
        return value


class ImportInput(Input):
    candidate_ids: list[int] = Field(min_length=1, max_length=20000)
    provenance: str = Field(default="Importazione locale", max_length=2000)
    license: str = Field(default="Da verificare", min_length=1, max_length=2000)


class GamePatch(Input):
    title: str = Field(min_length=1, max_length=300)
    author: str = Field(default="", max_length=500)
    publisher: str = Field(default="", max_length=500)
    region: str = Field(default="Sconosciuta", max_length=80)
    year: int | None = Field(default=None, ge=1970, le=2100)
    genre: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=20000)
    favorite: bool = False
    provenance: str = Field(default="Importazione locale", max_length=2000)
    license: str = Field(default="Da verificare", min_length=1, max_length=2000)
    cover_path: str = Field(default="", max_length=4096)


class FavoriteInput(Input):
    favorite: bool


class ExportInput(Input):
    game_ids: list[int] = Field(min_length=1, max_length=20000)
    dry_run: bool = True


class DownloadEntry(Input):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    title: str = Field(min_length=1, max_length=300)
    platform: str
    url: str = Field(max_length=4096)
    filename: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9 _().-]{0,150}$")
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    size: int = Field(gt=0, le=4 * 1024**3)
    license: str = Field(min_length=1, max_length=2000)
    rights_url: str = Field(min_length=1, max_length=4096)
    distribution: Literal["homebrew", "freeware", "public-domain"]
    redistribution_allowed: Literal[True]

    @field_validator("platform")
    @classmethod
    def platform_valid(cls, value):
        if value not in PLATFORMS:
            raise ValueError("Console non supportata")
        return value


class ProviderInput(Input):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    name: str = Field(min_length=1, max_length=120)
    entries: list[DownloadEntry] = Field(max_length=10000)
