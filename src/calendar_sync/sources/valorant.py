from __future__ import annotations

import fnmatch
import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from calendar_sync.config import ValorantConfig
from calendar_sync.http import JsonHttpClient, SourceRequestError
from calendar_sync.models import CanonicalEvent, SourceResult

VLR_ID_PATTERN = re.compile(r"vlr\.gg/(\d+)(?:/|$)", re.IGNORECASE)


class ValorantSource:
    feed = "valorant"

    def __init__(
        self,
        config: ValorantConfig,
        http: JsonHttpClient,
        fallback_fetcher: Callable[[], list[dict[str, Any]]] | None = None,
    ) -> None:
        self.config = config
        self.http = http
        self.fallback_fetcher = fallback_fetcher or self._fetch_vlrdevapi

    def fetch(self, now: datetime | None = None) -> SourceResult:
        current = now or datetime.now(UTC)
        try:
            payload = self.http.get_json(
                self.config.primary_url,
                params={"theme": "light"},
                headers={"Accept": "application/json"},
            )
            raw_matches = self._primary_matches(payload)
            if not raw_matches:
                raise SourceRequestError("primary Valorant provider returned no matches")
            events, warnings = self._normalise_many(raw_matches, "primary", current)
            return SourceResult(
                self.feed,
                "orlandomm",
                events,
                len(raw_matches),
                len(warnings),
                warnings,
            )
        except SourceRequestError as primary_error:
            try:
                raw_matches = self.fallback_fetcher()
                events, warnings = self._normalise_many(raw_matches, "fallback", current)
                return SourceResult(
                    self.feed,
                    self.config.fallback_provider,
                    events,
                    len(raw_matches),
                    len(warnings),
                    warnings,
                )
            except Exception as fallback_error:
                raise SourceRequestError(
                    f"both Valorant providers failed; primary={primary_error}; "
                    f"fallback={fallback_error}"
                ) from fallback_error

    @staticmethod
    def _primary_matches(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise SourceRequestError("primary Valorant response has an invalid schema")
        matches = payload["data"]
        if not all(isinstance(match, dict) for match in matches):
            raise SourceRequestError("primary Valorant matches must be objects")
        return cast(list[dict[str, Any]], matches)

    @staticmethod
    def _fetch_vlrdevapi() -> list[dict[str, Any]]:
        from vlrdevapi import VLRClient  # type: ignore[attr-defined]

        try:
            with VLRClient(timeout=15, max_retries=3, auto_detect_tz=True) as client:
                page = client.matches.upcoming(page=1)
        except Exception as error:
            raise SourceRequestError(f"vlrdevapi fallback failed: {error}") from error

        matches: list[dict[str, Any]] = []
        for match in page.matches:
            if match.datetime is None:
                continue
            link = match.url
            if link.startswith("/"):
                link = "https://www.vlr.gg" + link
            matches.append(
                {
                    "team1": match.team1.name if match.team1 else "TBD",
                    "team2": match.team2.name if match.team2 else "TBD",
                    "match_series": match.stage or "Upcoming match",
                    "match_event": match.event,
                    "match_page": link,
                    "unix_timestamp": match.datetime.isoformat(),
                }
            )
        if not matches:
            raise SourceRequestError("vlrdevapi fallback returned no usable upcoming matches")
        return matches

    def _normalise_many(
        self,
        matches: list[dict[str, Any]],
        provider: str,
        now: datetime,
    ) -> tuple[list[CanonicalEvent], list[str]]:
        events: list[CanonicalEvent] = []
        warnings: list[str] = []
        for raw in matches:
            try:
                event = (
                    self._normalise_primary(raw)
                    if provider == "primary"
                    else self._normalise_fallback(raw)
                )
            except (KeyError, TypeError, ValueError) as error:
                identifier = raw.get("id") or raw.get("match_page") or "unknown"
                warnings.append(f"{identifier}: {error}")
                continue
            if event is None or event.end_at is None or event.end_at <= now:
                continue
            if self._included(event):
                events.append(event)
        keys = [event.key for event in events]
        if len(keys) != len(set(keys)):
            raise SourceRequestError(f"{provider} Valorant response returned duplicate match IDs")
        return events, warnings

    def _normalise_primary(self, raw: dict[str, Any]) -> CanonicalEvent | None:
        if str(raw.get("status", "")).casefold() != "upcoming":
            return None
        teams = raw.get("teams")
        if not isinstance(teams, list) or len(teams) < 2:
            raise ValueError("missing teams")
        team1 = self._team_name(teams[0])
        team2 = self._team_name(teams[1])
        match_id = self._required_text(raw, "id")
        start = self._parse_primary_wall_clock(self._required_text(raw, "utc"))
        series = self._required_text(raw, "event")
        tournament = self._required_text(raw, "tournament")
        link = f"https://www.vlr.gg/{match_id}"
        return self._event(match_id, team1, team2, series, tournament, link, start)

    def _normalise_fallback(self, raw: dict[str, Any]) -> CanonicalEvent:
        team1 = self._required_text(raw, "team1")
        team2 = self._required_text(raw, "team2")
        series = self._required_text(raw, "match_series")
        tournament = self._required_text(raw, "match_event")
        link = self._required_text(raw, "match_page")
        start = self._parse_utc(self._required_text(raw, "unix_timestamp"))
        match_id = self._match_id(link, team1, team2, start)
        return self._event(match_id, team1, team2, series, tournament, link, start)

    def _event(
        self,
        match_id: str,
        team1: str,
        team2: str,
        series: str,
        tournament: str,
        link: str,
        start: datetime,
    ) -> CanonicalEvent:
        duration = (
            4 if "lower final" in series.casefold() or "grand final" in series.casefold() else 2
        )
        return CanonicalEvent(
            feed=self.feed,
            external_id=match_id,
            title=f"{team1} vs {team2} | {series}",
            description=f"Series: {series}\nEvent: {tournament}\n{link}",
            source_url=link,
            color_id=self.config.color_id,
            start_at=start,
            end_at=start + timedelta(hours=duration),
        )

    def _included(self, event: CanonicalEvent) -> bool:
        haystack = f"{event.title} {event.description}".casefold()
        excluded = any(
            fnmatch.fnmatch(haystack, pattern.casefold())
            for pattern in self.config.exclude_patterns
        )
        if excluded:
            return False
        return any(
            fnmatch.fnmatch(haystack, pattern.casefold())
            for pattern in self.config.include_patterns
        )

    def _parse_primary_wall_clock(self, value: str) -> datetime:
        """Correct the primary API's falsely UTC-labelled VLR wall-clock value."""
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        wall_clock = parsed.replace(tzinfo=None)
        return wall_clock.replace(
            tzinfo=ZoneInfo(self.config.primary_wall_clock_timezone)
        ).astimezone(UTC)

    @staticmethod
    def _parse_utc(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _team_name(raw: Any) -> str:
        if not isinstance(raw, dict):
            raise ValueError("missing team name")
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("missing team name")
        return name.strip()

    @staticmethod
    def _required_text(raw: dict[str, Any], key: str) -> str:
        value = raw.get(key)
        if value is None or not str(value).strip():
            raise ValueError(f"missing {key}")
        return str(value).strip()

    @staticmethod
    def _match_id(link: str, team1: str, team2: str, start: datetime) -> str:
        match = VLR_ID_PATTERN.search(link)
        if match:
            return match.group(1)
        stable = f"{link}|{team1}|{team2}|{start.isoformat()}".encode()
        return "fallback-" + hashlib.sha256(stable).hexdigest()[:24]
