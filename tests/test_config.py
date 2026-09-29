from pathlib import Path

import pytest
from pydantic import ValidationError

from calendar_sync.config import load_config

EXPECTED_POKEMON_WHITELIST = [
    "community-day",
    "event",
    "live-event",
    "pokemon-go-fest",
    "pokemon-spotlight-hour",
    "season",
    "pokemon-go-tour",
    "raid-day",
    "elite-raids",
    "raid-battles",
    "raid-hour",
    "raid-weekend",
    "research",
    "max-mondays",
    "max-battles",
]


def test_repository_config_is_valid() -> None:
    config = load_config(Path("config/feeds.yml"))

    assert config.version == 3
    assert config.timezone == "Europe/London"
    assert config.feeds.pokemon_go.enabled
    assert config.feeds.pokemon_go.future_start_only is True
    assert config.feeds.pokemon_go.include_event_types == EXPECTED_POKEMON_WHITELIST
    assert config.feeds.valorant.enabled
    assert config.feeds.valorant.primary_wall_clock_timezone == "America/New_York"


def test_all_day_types_must_also_be_included(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yml"
    path.write_text(
        """
version: 2
timezone: Europe/London
feeds:
  pokemon_go:
    calendar_id_env: POKEMON_CALENDAR
    source_url: https://example.test/pokemon
    color_id: '3'
    include_event_types: [event]
    all_day_event_types: [season]
  valorant:
    calendar_id_env: VALORANT_CALENDAR
    primary_url: https://example.test/primary
    fallback_provider: vlrdevapi
    color_id: '6'
    include_patterns: ['*VCT*']
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="all-day event types"):
        load_config(path)
