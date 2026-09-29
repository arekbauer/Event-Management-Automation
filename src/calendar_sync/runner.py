from __future__ import annotations

import logging
import os
from dataclasses import asdict
from typing import Any

from calendar_sync.calendar import GoogleCalendarGateway
from calendar_sync.config import AppConfig
from calendar_sync.http import JsonHttpClient
from calendar_sync.models import SourceResult, SyncStats
from calendar_sync.sources import PokemonSource, ValorantSource


class SyncRunner:
    def __init__(
        self,
        config: AppConfig,
        service: Any,
        logger: logging.Logger,
        http: JsonHttpClient,
    ) -> None:
        self.config = config
        self.gateway = GoogleCalendarGateway(service, config.timezone)
        self.logger = logger
        self.http = http

    def run(
        self,
        *,
        selected_feed: str = "all",
        dry_run: bool = False,
        allow_unsafe_deletes: bool = False,
        no_deletes: bool = False,
    ) -> tuple[list[SyncStats], list[str]]:
        stats: list[SyncStats] = []
        errors: list[str] = []
        for feed in self._selected_feeds(selected_feed):
            try:
                source = self._fetch(feed)
                for warning in source.warnings:
                    self.logger.warning("source_record_rejected feed=%s reason=%s", feed, warning)
                calendar_id = self._calendar_id(feed)
                result = self.gateway.reconcile(
                    calendar_id=calendar_id,
                    source=source,
                    safety=self.config.safety,
                    dry_run=dry_run,
                    allow_unsafe_deletes=allow_unsafe_deletes,
                    no_deletes=no_deletes,
                )
                stats.append(result)
                self.logger.info("sync_result %s", asdict(result))
            except Exception as error:
                message = f"{feed}: {type(error).__name__}: {error}"
                errors.append(message)
                self.logger.exception("feed_sync_failed feed=%s", feed)
        return stats, errors

    def calendar_ids(self) -> dict[str, str]:
        return {feed: self._calendar_id(feed) for feed in self._selected_feeds("all")}

    def _fetch(self, feed: str) -> SourceResult:
        if feed == "pokemon_go":
            return PokemonSource(
                self.config.feeds.pokemon_go,
                self.config.timezone,
                self.http,
            ).fetch()
        return ValorantSource(self.config.feeds.valorant, self.http).fetch()

    def _calendar_id(self, feed: str) -> str:
        config = getattr(self.config.feeds, feed)
        value = os.environ.get(config.calendar_id_env)
        if not value:
            raise ValueError(f"required environment variable {config.calendar_id_env} is not set")
        return value

    def _selected_feeds(self, selected: str) -> list[str]:
        choices = [
            name for name in ("pokemon_go", "valorant") if getattr(self.config.feeds, name).enabled
        ]
        if selected == "all":
            return choices
        if selected not in choices:
            raise ValueError(f"feed is disabled or unknown: {selected}")
        return [selected]
