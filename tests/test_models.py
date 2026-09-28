from datetime import UTC, date, datetime

import pytest

from calendar_sync.models import CanonicalEvent


def test_timed_event_is_serialised_as_utc() -> None:
    event = CanonicalEvent(
        feed="valorant",
        external_id="123",
        title="A vs B",
        description="Details",
        source_url="https://vlr.gg/123",
        color_id="6",
        start_at=datetime(2026, 9, 24, 18, tzinfo=UTC),
        end_at=datetime(2026, 9, 24, 20, tzinfo=UTC),
    )

    body = event.to_google_body("Europe/London")

    assert body["start"]["dateTime"] == "2026-09-24T18:00:00+00:00"
    assert body["extendedProperties"]["private"]["calendar_sync_external_id"] == "123"


def test_all_day_end_must_be_exclusive() -> None:
    with pytest.raises(ValueError, match="exclusive"):
        CanonicalEvent(
            feed="pokemon_go",
            external_id="event-1",
            title="Event",
            description="",
            source_url="https://example.test",
            color_id="3",
            start_date=date(2026, 9, 24),
            end_date=date(2026, 9, 24),
        )
