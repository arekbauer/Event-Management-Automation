from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SafetyConfig(StrictModel):
    max_deletions: int = Field(default=25, ge=0)
    max_deletion_fraction: float = Field(default=0.5, ge=0, le=1)


class FeedBase(StrictModel):
    enabled: bool = True
    calendar_id_env: str = Field(min_length=1)
    color_id: str = Field(pattern=r"^\d+$")


class PokemonConfig(FeedBase):
    source_url: str
    include_event_types: list[str] = Field(min_length=1)
    all_day_event_types: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def all_day_types_are_included(self) -> PokemonConfig:
        unknown = set(self.all_day_event_types) - set(self.include_event_types)
        if unknown:
            raise ValueError(f"all-day event types must also be included: {sorted(unknown)}")
        return self


class ValorantConfig(FeedBase):
    primary_url: str
    fallback_provider: str = Field(pattern=r"^vlrdevapi$")
    include_patterns: list[str] = Field(min_length=1)
    exclude_patterns: list[str] = Field(default_factory=list)


class FeedsConfig(StrictModel):
    pokemon_go: PokemonConfig
    valorant: ValorantConfig


class AppConfig(StrictModel):
    version: int = Field(ge=2, le=2)
    timezone: str = "Europe/London"
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    feeds: FeedsConfig

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"unknown IANA timezone: {value}") from error
        return value


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"could not read config {config_path}: {error}") from error
    return AppConfig.model_validate(raw)
