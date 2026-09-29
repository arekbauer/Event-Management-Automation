import sys
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from calendar_sync.config import ValorantConfig
from calendar_sync.http import JsonHttpClient, SourceRequestError
from calendar_sync.sources.valorant import ValorantSource


def config() -> ValorantConfig:
    return ValorantConfig(
        calendar_id_env="VALORANT_CALENDAR",
        primary_url="https://primary.test/matches",
        fallback_provider="vlrdevapi",
        color_id="6",
        include_patterns=["*valorant champions 2026*"],
        exclude_patterns=[],
    )


def test_primary_query_headers_and_falsely_labelled_summer_timestamp() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "12345",
                        "status": "Upcoming",
                        "utc": "2026-09-30T05:00:00Z",
                        "teams": [{"name": "Alpha"}, {"name": "Bravo"}],
                        "event": "Group Stage",
                        "tournament": "Valorant Champions 2026",
                    }
                ]
            },
        )

    http = JsonHttpClient(attempts=1, transport=httpx.MockTransport(handler))
    result = ValorantSource(config(), http).fetch(now=datetime(2026, 9, 1, tzinfo=UTC))

    assert seen[0].url.params["theme"] == "light"
    assert seen[0].headers["Accept"] == "application/json"
    assert result.events[0].start_at == datetime(2026, 9, 30, 9, tzinfo=UTC)
    assert result.events[0].external_id == "12345"


def test_primary_falsely_labelled_winter_timestamp_uses_standard_time() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "67890",
                        "status": "Upcoming",
                        "utc": "2026-12-01T05:00:00Z",
                        "teams": [{"name": "Alpha"}, {"name": "Bravo"}],
                        "event": "Group Stage",
                        "tournament": "Valorant Champions 2026",
                    }
                ]
            },
        )

    http = JsonHttpClient(attempts=1, transport=httpx.MockTransport(handler))
    result = ValorantSource(config(), http).fetch(now=datetime(2026, 9, 1, tzinfo=UTC))

    assert result.events[0].start_at == datetime(2026, 12, 1, 10, tzinfo=UTC)


def test_invalid_primary_uses_fallback_and_preserves_vlr_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"error": "bad gateway"})

    fallback = [
        {
            "team1": "Alpha",
            "team2": "Bravo",
            "match_series": "Grand Final",
            "match_event": "Valorant Champions 2026",
            "match_page": "https://www.vlr.gg/12345/example",
            "unix_timestamp": "2026-10-01 18:00:00",
        }
    ]

    http = JsonHttpClient(attempts=1, transport=httpx.MockTransport(handler))
    result = ValorantSource(config(), http, fallback_fetcher=lambda: fallback).fetch(
        now=datetime(2026, 9, 1, tzinfo=UTC)
    )

    assert result.provider == "vlrdevapi"
    assert result.events[0].external_id == "12345"
    assert result.events[0].end_at == datetime(2026, 10, 1, 22, tzinfo=UTC)


def test_vlrdevapi_fallback_enables_timezone_auto_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            options.update(kwargs)
            self.matches = SimpleNamespace(upcoming=lambda page: SimpleNamespace(matches=[]))

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setitem(sys.modules, "vlrdevapi", SimpleNamespace(VLRClient=FakeClient))

    with pytest.raises(SourceRequestError, match="no usable upcoming matches"):
        ValorantSource._fetch_vlrdevapi()

    assert options["auto_detect_tz"] is True
