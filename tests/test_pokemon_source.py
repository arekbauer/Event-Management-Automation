from datetime import UTC, datetime

import httpx

from calendar_sync.config import PokemonConfig
from calendar_sync.http import JsonHttpClient
from calendar_sync.sources.pokemon import PokemonSource


def source_for(payload: object) -> PokemonSource:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = PokemonConfig(
        calendar_id_env="POKEMON_CALENDAR",
        source_url="https://example.test/events.json",
        color_id="3",
        include_event_types=["community-day", "event", "pokemon-spotlight-hour", "raid-hour"],
        all_day_event_types=["event"],
    )
    return PokemonSource(
        config,
        "Europe/London",
        JsonHttpClient(attempts=1, transport=httpx.MockTransport(handler)),
    )


def test_naive_london_time_observes_dst() -> None:
    source = source_for(
        [
            {
                "eventID": "spotlight-1",
                "name": "Spotlight Hour",
                "eventType": "pokemon-spotlight-hour",
                "link": "https://example.test/event",
                "start": "2026-07-14T18:00:00.000",
                "end": "2026-07-14T19:00:00.000",
                "extraData": {},
            }
        ]
    )

    result = source.fetch(now=datetime(2026, 7, 1, tzinfo=UTC))

    assert result.events[0].start_at == datetime(2026, 7, 14, 17, tzinfo=UTC)
    assert result.events[0].end_at == datetime(2026, 7, 14, 18, tzinfo=UTC)


def test_configured_all_day_event_is_limited_to_its_start_date() -> None:
    source = source_for(
        [
            {
                "eventID": "festival-1",
                "name": "Festival",
                "eventType": "event",
                "link": "https://example.test/festival",
                "start": "2026-10-02T10:00:00.000",
                "end": "2026-10-05T20:00:00.000",
                "extraData": {},
            }
        ]
    )

    event = source.fetch(now=datetime(2026, 9, 1, tzinfo=UTC)).events[0]

    assert event.start_date.isoformat() == "2026-10-02"
    assert event.end_date.isoformat() == "2026-10-03"


def test_raid_hour_keeps_source_start_and_end_times() -> None:
    source = source_for(
        [
            {
                "eventID": "raid-hour-1",
                "name": "Tornadus Raid Hour",
                "eventType": "raid-hour",
                "link": "https://example.test/raid-hour",
                "start": "2026-10-07T18:00:00.000",
                "end": "2026-10-07T19:00:00.000",
                "extraData": {},
            }
        ]
    )

    event = source.fetch(now=datetime(2026, 10, 1, tzinfo=UTC)).events[0]

    assert event.start_at == datetime(2026, 10, 7, 17, tzinfo=UTC)
    assert event.end_at == datetime(2026, 10, 7, 18, tzinfo=UTC)
    assert event.start_date is None
    assert event.end_date is None


def test_community_day_keeps_source_start_and_end_times() -> None:
    source = source_for(
        [
            {
                "eventID": "community-day-1",
                "name": "February Community Day",
                "eventType": "community-day",
                "link": "https://example.test/community-day",
                "start": "2026-10-11T14:00:00.000",
                "end": "2026-10-11T17:00:00.000",
                "extraData": {},
            }
        ]
    )

    event = source.fetch(now=datetime(2026, 10, 1, tzinfo=UTC)).events[0]

    assert event.start_at == datetime(2026, 10, 11, 13, tzinfo=UTC)
    assert event.end_at == datetime(2026, 10, 11, 16, tzinfo=UTC)
    assert event.start_date is None
    assert event.end_date is None


def test_ambiguous_autumn_time_uses_later_instant() -> None:
    source = source_for(
        [
            {
                "eventID": "clock-change",
                "name": "Clock Change",
                "eventType": "pokemon-spotlight-hour",
                "link": "https://example.test/clock",
                "start": "2026-10-25T01:30:00.000",
                "end": "2026-10-25T02:30:00.000",
                "extraData": {},
            }
        ]
    )

    event = source.fetch(now=datetime(2026, 10, 1, tzinfo=UTC)).events[0]

    assert event.start_at == datetime(2026, 10, 25, 1, 30, tzinfo=UTC)


def test_nonexistent_spring_time_is_rejected() -> None:
    source = source_for(
        [
            {
                "eventID": "clock-change",
                "name": "Clock Change",
                "eventType": "pokemon-spotlight-hour",
                "link": "https://example.test/clock",
                "start": "2026-03-29T01:30:00.000",
                "end": "2026-03-29T02:30:00.000",
                "extraData": {},
            }
        ]
    )

    result = source.fetch(now=datetime(2026, 3, 1, tzinfo=UTC))

    assert result.events == []
    assert result.rejected_count == 1


def test_event_starting_today_is_excluded_like_v1() -> None:
    source = source_for(
        [
            {
                "eventID": "ongoing-1",
                "name": "Ongoing Event",
                "eventType": "event",
                "link": "https://example.test/ongoing",
                "start": "2026-09-28T08:00:00.000",
                "end": "2026-10-05T20:00:00.000",
                "extraData": {},
            }
        ]
    )

    result = source.fetch(now=datetime(2026, 9, 28, 12, tzinfo=UTC))

    assert result.events == []
