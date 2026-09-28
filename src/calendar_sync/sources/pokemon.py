from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from calendar_sync.config import PokemonConfig
from calendar_sync.http import JsonHttpClient, SourceRequestError
from calendar_sync.models import CanonicalEvent, SourceResult


class PokemonSource:
    feed = "pokemon_go"

    def __init__(
        self,
        config: PokemonConfig,
        timezone_name: str,
        http: JsonHttpClient,
    ) -> None:
        self.config = config
        self.timezone = ZoneInfo(timezone_name)
        self.http = http

    def fetch(self, now: datetime | None = None) -> SourceResult:
        payload = self.http.get_json(
            self.config.source_url,
            headers={"Accept": "application/json"},
        )
        if not isinstance(payload, list):
            raise SourceRequestError("Pokemon source response must be a JSON array")

        current = now or datetime.now(UTC)
        events: list[CanonicalEvent] = []
        warnings: list[str] = []
        for raw in payload:
            if not isinstance(raw, dict):
                warnings.append("record without an object schema")
                continue
            event_type = raw.get("eventType")
            if event_type not in self.config.include_event_types:
                continue
            try:
                event = self._normalise(raw, str(event_type))
            except (KeyError, TypeError, ValueError) as error:
                identifier = raw.get("eventID", "unknown")
                warnings.append(f"{identifier}: {error}")
                continue
            if self.config.future_start_only and self._started_today_or_earlier(event, current):
                continue
            if self._is_finished(event, current):
                continue
            events.append(event)

        self._assert_unique(events)
        return SourceResult(
            feed=self.feed,
            provider="scrapedduck",
            events=events,
            raw_count=len(payload),
            rejected_count=len(warnings),
            warnings=warnings,
        )

    def _normalise(self, raw: dict[str, Any], event_type: str) -> CanonicalEvent:
        external_id = self._required_text(raw, "eventID")
        title = self._required_text(raw, "name")
        link = self._required_text(raw, "link")
        start = self._parse_datetime(self._required_text(raw, "start"))
        end = self._parse_datetime(self._required_text(raw, "end"))
        description = self._description(raw, link)

        if event_type in self.config.all_day_event_types:
            start_date = start.astimezone(self.timezone).date()
            return CanonicalEvent(
                feed=self.feed,
                external_id=external_id,
                title=title,
                description=description,
                source_url=link,
                color_id=self.config.color_id,
                start_date=start_date,
                end_date=start_date + timedelta(days=1),
            )
        return CanonicalEvent(
            feed=self.feed,
            external_id=external_id,
            title=title,
            description=description,
            source_url=link,
            color_id=self.config.color_id,
            start_at=start.astimezone(UTC),
            end_at=end.astimezone(UTC),
        )

    def _parse_datetime(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = self._localise_wall_time(parsed)
        return parsed

    def _localise_wall_time(self, value: datetime) -> datetime:
        candidates = [value.replace(tzinfo=self.timezone, fold=fold) for fold in (0, 1)]
        valid = [
            candidate
            for candidate in candidates
            if candidate.astimezone(UTC).astimezone(self.timezone).replace(tzinfo=None) == value
        ]
        if not valid:
            raise ValueError(f"nonexistent local time in {self.timezone.key}: {value.isoformat()}")
        if len(valid) == 2 and valid[0].utcoffset() != valid[1].utcoffset():
            return valid[1]  # Prefer the later instant when the clock repeats an hour.
        return valid[0]

    @staticmethod
    def _required_text(raw: dict[str, Any], key: str) -> str:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"missing {key}")
        return value.strip()

    @staticmethod
    def _description(raw: dict[str, Any], link: str) -> str:
        extra = raw.get("extraData") or {}
        lines: list[str] = []
        community = extra.get("communityday") or {}
        bonuses = community.get("bonuses") or []
        lines.extend(
            str(item["text"]) for item in bonuses if isinstance(item, dict) and item.get("text")
        )

        spotlight = extra.get("spotlight") or {}
        if spotlight:
            if spotlight.get("name"):
                lines.append(f"Pokemon: {spotlight['name']}")
            if "canBeShiny" in spotlight:
                lines.append(f"Shiny: {'yes' if spotlight['canBeShiny'] else 'no'}")
            if spotlight.get("bonus"):
                lines.append(f"Bonus: {spotlight['bonus']}")

        bosses = (extra.get("raidbattles") or {}).get("bosses") or []
        for boss in bosses:
            if isinstance(boss, dict) and boss.get("name"):
                shiny = "yes" if boss.get("canBeShiny") else "no"
                lines.append(f"{boss['name']} - Shiny: {shiny}")
        lines.append(link)
        return "\n".join(lines)

    def _is_finished(self, event: CanonicalEvent, now: datetime) -> bool:
        if event.end_at is not None:
            return event.end_at <= now.astimezone(UTC)
        assert event.end_date is not None
        return event.end_date <= now.astimezone(self.timezone).date()

    def _started_today_or_earlier(self, event: CanonicalEvent, now: datetime) -> bool:
        today = now.astimezone(self.timezone).date()
        if event.start_at is not None:
            return event.start_at.astimezone(self.timezone).date() <= today
        assert event.start_date is not None
        return event.start_date <= today

    @staticmethod
    def _assert_unique(events: list[CanonicalEvent]) -> None:
        keys = [event.key for event in events]
        if len(keys) != len(set(keys)):
            raise SourceRequestError("Pokemon source returned duplicate event IDs")
