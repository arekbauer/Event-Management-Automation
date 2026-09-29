import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from calendar_sync.calendar import GoogleCalendarGateway, ReconciliationSafetyError
from calendar_sync.config import SafetyConfig
from calendar_sync.models import CanonicalEvent, SourceResult


class Response:
    def __init__(self, value: Any) -> None:
        self.value = value

    def execute(self) -> Any:
        return self.value


class FakeEvents:
    def __init__(self, listed: list[dict[str, Any]]) -> None:
        self.listed = listed
        self.created: list[dict[str, Any]] = []
        self.updated: list[tuple[str, dict[str, Any]]] = []
        self.deleted: list[str] = []

    def list(self, **_: Any) -> Response:
        return Response({"items": self.listed})

    def insert(self, *, body: dict[str, Any], **_: Any) -> Response:
        self.created.append(body)
        return Response(body)

    def update(self, *, eventId: str, body: dict[str, Any], **_: Any) -> Response:
        self.updated.append((eventId, body))
        return Response(body)

    def delete(self, *, eventId: str, **_: Any) -> Response:
        self.deleted.append(eventId)
        return Response({})


class FakeService:
    def __init__(self, listed: list[dict[str, Any]]) -> None:
        self.resource = FakeEvents(listed)

    def events(self) -> FakeEvents:
        return self.resource


def desired_event(title: str = "Alpha vs Bravo") -> CanonicalEvent:
    return CanonicalEvent(
        feed="valorant",
        external_id="123",
        title=title,
        description="Event details",
        source_url="https://vlr.gg/123",
        color_id="6",
        start_at=datetime(2026, 10, 1, 18, tzinfo=UTC),
        end_at=datetime(2026, 10, 1, 20, tzinfo=UTC),
    )


def source(events: list[CanonicalEvent]) -> SourceResult:
    return SourceResult("valorant", "test", events, len(events))


def existing_from(event: CanonicalEvent, event_id: str = "google-1") -> dict[str, Any]:
    return {"id": event_id, **event.to_google_body("Europe/London")}


def test_second_unchanged_run_performs_no_writes() -> None:
    event = desired_event()
    service = FakeService([existing_from(event)])
    gateway = GoogleCalendarGateway(service, "Europe/London")

    stats = gateway.reconcile(
        calendar_id="calendar",
        source=source([event]),
        safety=SafetyConfig(),
        now=datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert stats.unchanged == 1
    assert not service.resource.created
    assert not service.resource.updated
    assert not service.resource.deleted


def test_changed_event_is_updated_and_new_event_is_created() -> None:
    changed = desired_event("Updated title")
    old = existing_from(desired_event())
    new = CanonicalEvent(
        feed="valorant",
        external_id="456",
        title="Charlie vs Delta",
        description="Details",
        source_url="https://vlr.gg/456",
        color_id="6",
        start_at=datetime(2026, 10, 2, 18, tzinfo=UTC),
        end_at=datetime(2026, 10, 2, 20, tzinfo=UTC),
    )
    service = FakeService([old])

    stats = GoogleCalendarGateway(service, "Europe/London").reconcile(
        calendar_id="calendar",
        source=source([changed, new]),
        safety=SafetyConfig(),
        now=datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert stats.created == 1
    assert stats.updated == 1
    assert service.resource.updated[0][0] == "google-1"


def test_all_day_event_can_be_replaced_with_timed_event() -> None:
    previous = CanonicalEvent(
        feed="valorant",
        external_id="123",
        title="Alpha vs Bravo",
        description="Event details",
        source_url="https://vlr.gg/123",
        color_id="6",
        start_date=datetime(2026, 10, 1, tzinfo=UTC).date(),
        end_date=datetime(2026, 10, 2, tzinfo=UTC).date(),
    )
    service = FakeService([existing_from(previous)])

    stats = GoogleCalendarGateway(service, "Europe/London").reconcile(
        calendar_id="calendar",
        source=source([desired_event()]),
        safety=SafetyConfig(),
        now=datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert stats.updated == 1
    updated_body = service.resource.updated[0][1]
    assert "date" not in updated_body["start"]
    assert updated_body["start"]["dateTime"] == "2026-10-01T18:00:00+00:00"
    assert "date" not in updated_body["end"]
    assert updated_body["end"]["dateTime"] == "2026-10-01T20:00:00+00:00"


def test_empty_desired_set_blocks_deletion() -> None:
    service = FakeService([existing_from(desired_event())])

    with pytest.raises(ReconciliationSafetyError, match="desired event set is empty"):
        GoogleCalendarGateway(service, "Europe/London").reconcile(
            calendar_id="calendar",
            source=source([]),
            safety=SafetyConfig(),
            now=datetime(2026, 9, 1, tzinfo=UTC),
        )


def test_dry_run_reports_without_writing() -> None:
    service = FakeService([])

    stats = GoogleCalendarGateway(service, "Europe/London").reconcile(
        calendar_id="calendar",
        source=source([desired_event()]),
        safety=SafetyConfig(),
        dry_run=True,
        now=datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert stats.created == 1
    assert not service.resource.created


def test_no_deletes_applies_updates_and_reports_preserved_stale_events() -> None:
    changed = desired_event("Corrected title")
    stale = CanonicalEvent(
        feed="valorant",
        external_id="stale-456",
        title="Stale fixture",
        description="Old source data",
        source_url="https://vlr.gg/456",
        color_id="6",
        start_at=datetime(2026, 10, 2, 18, tzinfo=UTC),
        end_at=datetime(2026, 10, 2, 20, tzinfo=UTC),
    )
    service = FakeService(
        [existing_from(desired_event()), existing_from(stale, event_id="google-stale")]
    )

    stats = GoogleCalendarGateway(service, "Europe/London").reconcile(
        calendar_id="calendar",
        source=source([changed]),
        safety=SafetyConfig(max_deletions=0, max_deletion_fraction=0),
        no_deletes=True,
        now=datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert stats.updated == 1
    assert stats.deleted == 0
    assert stats.deletions_skipped == 1
    assert service.resource.updated[0][0] == "google-1"
    assert service.resource.deleted == []


def test_manual_event_is_never_deleted() -> None:
    manual = {
        "id": "manual-1",
        "summary": "Personal event",
        "start": {"dateTime": "2026-10-01T10:00:00Z"},
        "end": {"dateTime": "2026-10-01T11:00:00Z"},
    }
    service = FakeService([manual])

    stats = GoogleCalendarGateway(service, "Europe/London").reconcile(
        calendar_id="calendar",
        source=source([desired_event()]),
        safety=SafetyConfig(),
        now=datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert stats.created == 1
    assert service.resource.deleted == []


def test_migration_backup_is_written_before_events_are_deleted(tmp_path: Path) -> None:
    old = existing_from(desired_event(), event_id="legacy-1")
    service = FakeService([old])
    path = tmp_path / "backup.json"

    count = GoogleCalendarGateway(service, "Europe/London").backup_and_clear_future(
        {"valorant": "calendar"},
        path,
        now=datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert count == 1
    assert json.loads(path.read_text(encoding="utf-8"))["valorant"][0]["id"] == "legacy-1"
    assert service.resource.deleted == ["legacy-1"]


def test_restore_uses_only_writable_calendar_fields(tmp_path: Path) -> None:
    backup = {
        "valorant": [
            {
                "id": "old-google-id",
                "etag": "read-only",
                **desired_event().to_google_body("Europe/London"),
            }
        ]
    }
    path = tmp_path / "backup.json"
    path.write_text(json.dumps(backup), encoding="utf-8")
    service = FakeService([])

    restored = GoogleCalendarGateway(service, "Europe/London").restore_backup(
        {"valorant": "calendar"}, path
    )

    assert restored == 1
    assert "id" not in service.resource.created[0]
    assert "etag" not in service.resource.created[0]
