from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from calendar_sync.config import SafetyConfig
from calendar_sync.models import (
    APP_PROPERTY,
    APP_PROPERTY_VALUE,
    FEED_PROPERTY,
    ID_PROPERTY,
    CanonicalEvent,
    SourceResult,
    SyncStats,
)


class ReconciliationSafetyError(RuntimeError):
    pass


class GoogleCalendarGateway:
    def __init__(self, service: Any, timezone_name: str) -> None:
        self.service = service
        self.timezone_name = timezone_name
        self.timezone = ZoneInfo(timezone_name)

    def reconcile(
        self,
        *,
        calendar_id: str,
        source: SourceResult,
        safety: SafetyConfig,
        dry_run: bool = False,
        allow_unsafe_deletes: bool = False,
        no_deletes: bool = False,
        now: datetime | None = None,
    ) -> SyncStats:
        current = now or datetime.now(UTC)
        existing = self.list_managed(calendar_id, source.feed)
        desired = {event.external_id: event for event in source.events}
        if len(desired) != len(source.events):
            raise ReconciliationSafetyError(f"duplicate desired IDs for {source.feed}")

        existing_by_id: dict[str, dict[str, Any]] = {}
        for existing_event in existing:
            external_id = self._private_properties(existing_event).get(ID_PROPERTY)
            if not external_id:
                continue
            if external_id in existing_by_id:
                raise ReconciliationSafetyError(
                    f"duplicate managed Google events for {source.feed}:{external_id}"
                )
            existing_by_id[external_id] = existing_event

        to_create = [event for key, event in desired.items() if key not in existing_by_id]
        to_update: list[tuple[dict[str, Any], CanonicalEvent]] = []
        unchanged = 0
        for key, desired_event in desired.items():
            old = existing_by_id.get(key)
            if old is None:
                continue
            body = desired_event.to_google_body(self.timezone_name)
            if self._signature(old) == self._signature(body):
                unchanged += 1
            else:
                to_update.append((old, desired_event))

        stale_candidates = [
            old
            for key, old in existing_by_id.items()
            if key not in desired and self._is_current_or_future(old, current)
        ]
        stale = [] if no_deletes else stale_candidates
        self._check_deletions(
            stale_count=len(stale),
            existing_count=len(existing_by_id),
            desired_count=len(desired),
            safety=safety,
            allow_unsafe=allow_unsafe_deletes,
            feed=source.feed,
        )

        if not dry_run:
            for desired_event in to_create:
                self.service.events().insert(
                    calendarId=calendar_id,
                    body=desired_event.to_google_body(self.timezone_name),
                ).execute()
            for old, desired_event in to_update:
                self.service.events().update(
                    calendarId=calendar_id,
                    eventId=old["id"],
                    body=desired_event.to_google_body(self.timezone_name),
                ).execute()
            for old in stale:
                self.service.events().delete(
                    calendarId=calendar_id,
                    eventId=old["id"],
                ).execute()

        return SyncStats(
            feed=source.feed,
            provider=source.provider,
            fetched=source.raw_count,
            desired=len(desired),
            rejected=source.rejected_count,
            created=len(to_create),
            updated=len(to_update),
            deleted=len(stale),
            deletions_skipped=len(stale_candidates) if no_deletes else 0,
            unchanged=unchanged,
            dry_run=dry_run,
        )

    def list_managed(self, calendar_id: str, feed: str) -> list[dict[str, Any]]:
        managed = self._list_events(
            calendar_id,
            privateExtendedProperty=f"{APP_PROPERTY}={APP_PROPERTY_VALUE}",
            showDeleted=False,
            singleEvents=True,
        )
        return [
            event for event in managed if self._private_properties(event).get(FEED_PROPERTY) == feed
        ]

    def backup_and_clear_future(
        self,
        calendar_ids: dict[str, str],
        backup_path: str | Path,
        *,
        now: datetime | None = None,
    ) -> int:
        current = now or datetime.now(UTC)
        backup: dict[str, list[dict[str, Any]]] = {}
        count = 0
        for feed, calendar_id in calendar_ids.items():
            events = self._list_events(
                calendar_id,
                timeMin=current.isoformat(),
                showDeleted=False,
                singleEvents=True,
                orderBy="startTime",
            )
            backup[feed] = events
            count += len(events)
        path = Path(backup_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(backup, indent=2), encoding="utf-8")

        for feed, events in backup.items():
            calendar_id = calendar_ids[feed]
            for event in events:
                self.service.events().delete(
                    calendarId=calendar_id,
                    eventId=event["id"],
                ).execute()
        return count

    def restore_backup(self, calendar_ids: dict[str, str], backup_path: str | Path) -> int:
        raw = json.loads(Path(backup_path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("backup must contain a feed-to-events object")
        restored = 0
        writable = {
            "summary",
            "description",
            "location",
            "start",
            "end",
            "colorId",
            "reminders",
            "extendedProperties",
            "transparency",
            "visibility",
            "recurrence",
        }
        for feed, events in raw.items():
            if feed not in calendar_ids or not isinstance(events, list):
                raise ValueError(f"invalid or unknown feed in backup: {feed}")
            for event in events:
                if not isinstance(event, dict):
                    raise ValueError("backup events must be objects")
                body = {key: value for key, value in event.items() if key in writable}
                self.service.events().insert(calendarId=calendar_ids[feed], body=body).execute()
                restored += 1
        return restored

    def _list_events(self, calendar_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            request = self.service.events().list(
                calendarId=calendar_id,
                pageToken=page_token,
                **kwargs,
            )
            response = request.execute()
            events.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return events

    @staticmethod
    def _private_properties(event: dict[str, Any]) -> dict[str, str]:
        properties = event.get("extendedProperties", {}).get("private", {})
        return properties if isinstance(properties, dict) else {}

    def _is_current_or_future(self, event: dict[str, Any], now: datetime) -> bool:
        end = event.get("end", {})
        if end.get("dateTime"):
            parsed = datetime.fromisoformat(str(end["dateTime"]).replace("Z", "+00:00"))
            return parsed.astimezone(UTC) > now.astimezone(UTC)
        if end.get("date"):
            return date.fromisoformat(str(end["date"])) > now.astimezone(self.timezone).date()
        return False

    @staticmethod
    def _check_deletions(
        *,
        stale_count: int,
        existing_count: int,
        desired_count: int,
        safety: SafetyConfig,
        allow_unsafe: bool,
        feed: str,
    ) -> None:
        if stale_count == 0 or allow_unsafe:
            return
        fraction = stale_count / max(1, existing_count)
        reasons: list[str] = []
        if desired_count == 0:
            reasons.append("desired event set is empty")
        if stale_count > safety.max_deletions:
            reasons.append(f"{stale_count} deletions exceed limit {safety.max_deletions}")
        if fraction > safety.max_deletion_fraction:
            reasons.append(
                f"deletion fraction {fraction:.0%} exceeds limit {safety.max_deletion_fraction:.0%}"
            )
        if reasons:
            raise ReconciliationSafetyError(f"refusing unsafe {feed} sync: {'; '.join(reasons)}")

    @staticmethod
    def _signature(event: dict[str, Any]) -> dict[str, Any]:
        start = GoogleCalendarGateway._normalise_endpoint(event.get("start", {}))
        end = GoogleCalendarGateway._normalise_endpoint(event.get("end", {}))
        private = event.get("extendedProperties", {}).get("private", {})
        return {
            "summary": event.get("summary", ""),
            "description": event.get("description", ""),
            "colorId": str(event.get("colorId", "")),
            "start": start,
            "end": end,
            "reminders": event.get("reminders", {"useDefault": False}),
            "private": private,
        }

    @staticmethod
    def _normalise_endpoint(endpoint: dict[str, Any]) -> dict[str, str]:
        if endpoint.get("date"):
            return {"date": str(endpoint["date"])}
        value = endpoint.get("dateTime")
        if value:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return {"dateTime": parsed.astimezone(UTC).isoformat()}
        return {}
