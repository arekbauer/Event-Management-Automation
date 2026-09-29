from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

APP_PROPERTY = "calendar_sync_app"
FEED_PROPERTY = "calendar_sync_feed"
ID_PROPERTY = "calendar_sync_external_id"
APP_PROPERTY_VALUE = "v2"


@dataclass(frozen=True, slots=True)
class CanonicalEvent:
    feed: str
    external_id: str
    title: str
    description: str
    source_url: str
    color_id: str
    start_at: datetime | None = None
    end_at: datetime | None = None
    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self) -> None:
        timed = self.start_at is not None or self.end_at is not None
        all_day = self.start_date is not None or self.end_date is not None
        if timed == all_day:
            raise ValueError("event must be either timed or all-day")
        if timed:
            if self.start_at is None or self.end_at is None:
                raise ValueError("timed event requires both timestamps")
            if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
                raise ValueError("timed event timestamps must be timezone-aware")
            if self.end_at <= self.start_at:
                raise ValueError("event end must be after its start")
        elif self.start_date is None or self.end_date is None or self.end_date <= self.start_date:
            raise ValueError("all-day end date must be exclusive and after start date")
        if not self.feed or not self.external_id or not self.title:
            raise ValueError("feed, external ID and title are required")

    @property
    def key(self) -> str:
        return f"{self.feed}:{self.external_id}"

    def to_google_body(self, timezone_name: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "summary": self.title,
            "description": self.description,
            "colorId": self.color_id,
            "reminders": {"useDefault": False},
            "extendedProperties": {
                "private": {
                    APP_PROPERTY: APP_PROPERTY_VALUE,
                    FEED_PROPERTY: self.feed,
                    ID_PROPERTY: self.external_id,
                }
            },
        }
        if self.start_at is not None and self.end_at is not None:
            body["start"] = {
                "dateTime": self.start_at.astimezone(UTC).isoformat(),
                "timeZone": timezone_name,
            }
            body["end"] = {
                "dateTime": self.end_at.astimezone(UTC).isoformat(),
                "timeZone": timezone_name,
            }
        else:
            assert self.start_date is not None
            assert self.end_date is not None
            body["start"] = {"date": self.start_date.isoformat()}
            body["end"] = {"date": self.end_date.isoformat()}
        return body


@dataclass(frozen=True, slots=True)
class SourceResult:
    feed: str
    provider: str
    events: list[CanonicalEvent]
    raw_count: int
    rejected_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SyncStats:
    feed: str
    provider: str
    fetched: int
    desired: int
    rejected: int
    created: int
    updated: int
    deleted: int
    deletions_skipped: int
    unchanged: int
    dry_run: bool
