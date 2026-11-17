from typing import Literal

from pydantic import Field

from backend.schemas import Input


class CurationInput(Input):
    mode: Literal["auto", "include", "exclude"] = "auto"
    classic_id: str | None = Field(default=None, max_length=64)
    identity_confirmed: bool = False
    position: int = Field(default=0, ge=0, le=1000000)


class MetadataReviewInput(Input):
    status: Literal["unverified", "review", "verified"]
    note: str = Field(default="", max_length=2000)


class MediaPreviewInput(Input):
    game_ids: list[int] = Field(default_factory=list, max_length=20000)
    replace_existing: bool = False


class MediaApplyInput(Input):
    candidate_ids: list[str] = Field(min_length=1, max_length=20000)
    confirmed: Literal[True]


class LocalMediaInput(Input):
    kind: Literal["cover", "screenshot"]
    path: str = Field(min_length=1, max_length=4096)
    rights_confirmed: Literal[True]
    identity_confirmed: Literal[True]
    source: str = Field(min_length=3, max_length=2000)
    license: str = Field(min_length=3, max_length=300)


class CollectionSyncInput(Input):
    device_id: str = Field(min_length=1, max_length=36)
