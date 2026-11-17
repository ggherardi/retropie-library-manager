from typing import Literal

from pydantic import Field, model_validator

from backend.schemas import Input


class DiscoveryFilters(Input):
    q: str = Field(default="", max_length=300)
    platforms: list[str] = Field(default_factory=list, max_length=20)
    sources: list[str] = Field(default_factory=list, max_length=50)
    licenses: list[str] = Field(default_factory=list, max_length=100)
    genre: str = Field(default="", max_length=120)
    available_only: bool = False


class AcquisitionSettings(Input):
    target_bytes: int = Field(default=32_000_000_000, ge=1_000_000_000, le=8_000_000_000_000)
    reserved_bytes: int = Field(default=8_000_000_000, ge=0)
    filesystem_margin_percent: int = Field(default=5, ge=0, le=30)
    concurrency: int = Field(default=2, ge=1, le=8)
    automatic_filters: DiscoveryFilters = Field(default_factory=DiscoveryFilters)
    automatic_max_bytes: int = Field(default=2_000_000_000, ge=1, le=8_000_000_000_000)
    exclude_duplicates: bool = True

    @model_validator(mode="after")
    def valid_capacity(self):
        if self.reserved_bytes >= self.target_bytes * (1 - self.filesystem_margin_percent / 100):
            raise ValueError("La riserva deve essere inferiore alla capacità utile")
        return self


class PlanInput(Input):
    mode: Literal["manual", "automatic"] = "manual"
    ids: list[str] = Field(default_factory=list, max_length=20000)
    all_filtered: bool = False
    filters: DiscoveryFilters = Field(default_factory=DiscoveryFilters)


class Confirmation(Input):
    confirmed: Literal[True]


class TaskAction(Input):
    action: Literal["pause", "resume", "cancel", "retry"]


class EnrichInput(Input):
    game_ids: list[int] = Field(default_factory=list, max_length=20000)
    apply: bool = False
    covers: bool = True
