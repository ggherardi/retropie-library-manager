from typing import Literal

from pydantic import Field

from backend.schemas import Input


class LocalInstallInput(Input):
    paths: list[str] = Field(min_length=1, max_length=20000)
    recursive: bool = True
    mode: Literal["install", "local"] = "install"
    device_id: str = ""
    request_key: str = Field(min_length=8, max_length=100)


class UploadDescriptor(Input):
    relative: str = Field(min_length=1, max_length=1000)
    size: int = Field(ge=0, le=16 * 1024**3)


class UploadInstallInput(Input):
    files: list[UploadDescriptor] = Field(min_length=1, max_length=20000)
    mode: Literal["install", "local"] = "install"
    device_id: str = ""
    recursive: bool = True
    request_key: str = Field(min_length=8, max_length=100)


class InstallationConfirm(Input):
    confirmed: Literal[True]
    rights_confirmed: Literal[True]
    keep_local_when_offline: bool = True
    enrich: bool = True


class InstallationDecision(Input):
    action: Literal["choose", "skip"]
    platform: str = ""
    title: str = Field(default="", max_length=300)
    confirmed_title: bool = False
    entry_uid: str = ""
    variant_source: str = Field(default="", max_length=4096)
    archive_mode: Literal["split", "merged", "non-merged", "full-non-merged"] = "non-merged"


class InstallationControl(Input):
    action: Literal["pause", "resume", "retry", "cancel", "refresh"]


class VisibilityInput(Input):
    confirmed: Literal[True]
    metadata_review: bool = False
