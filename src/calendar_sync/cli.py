from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from calendar_sync.calendar import GoogleCalendarGateway
from calendar_sync.config import AppConfig, load_config
from calendar_sync.http import JsonHttpClient
from calendar_sync.logging import configure_logging
from calendar_sync.notify import notify_discord
from calendar_sync.runner import SyncRunner
from calendar_sync.sources import PokemonSource, ValorantSource

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="calendar-sync")
    parser.add_argument("--config", default="config/feeds.yml", help="path to YAML config")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("validate-config", help="validate configuration and exit")

    smoke = subcommands.add_parser("source-smoke", help="validate live sources without Google")
    smoke.add_argument("--feed", choices=["all", "pokemon_go", "valorant"], default="all")

    sync = subcommands.add_parser("sync", help="reconcile upstream events with Google Calendar")
    sync.add_argument("--feed", choices=["all", "pokemon_go", "valorant"], default="all")
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument("--allow-unsafe-deletes", action="store_true")

    migrate = subcommands.add_parser("migrate-v1", help="one-time v1 future-event rebuild")
    migrate.add_argument("--backup", required=True)
    migrate.add_argument(
        "--confirm-rebuild",
        required=True,
        help="must be exactly DELETE_FUTURE_EVENTS",
    )

    restore = subcommands.add_parser("restore-backup", help="restore a migration JSON backup")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--confirm-restore", required=True, help="must be exactly RESTORE_EVENTS")
    return parser


def google_calendar_service() -> Any:
    import google.auth
    from googleapiclient.discovery import build  # type: ignore[import-untyped]

    credentials, _ = google.auth.default(scopes=[CALENDAR_SCOPE])
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def run_sync(
    config: AppConfig,
    args: argparse.Namespace,
    logger: Any,
    service: Any,
) -> int:
    with JsonHttpClient() as http:
        runner = SyncRunner(config, service, logger, http)
        stats, errors = runner.run(
            selected_feed=args.feed,
            dry_run=args.dry_run,
            allow_unsafe_deletes=args.allow_unsafe_deletes,
        )
    print(json.dumps({"results": [vars_stat(stat) for stat in stats], "errors": errors}, indent=2))
    if errors:
        notify_discord(
            os.environ.get("DISCORD_WEBHOOK_URL"),
            "Calendar sync failed:\n" + "\n".join(errors),
            logger,
        )
        return 1
    return 0


def run_source_smoke(config: AppConfig, selected_feed: str) -> int:
    selected = ["pokemon_go", "valorant"] if selected_feed == "all" else [selected_feed]
    results: list[dict[str, Any]] = []
    with JsonHttpClient() as http:
        for feed in selected:
            feed_config = getattr(config.feeds, feed)
            if not feed_config.enabled:
                continue
            if feed == "pokemon_go":
                result = PokemonSource(feed_config, config.timezone, http).fetch()
            else:
                result = ValorantSource(feed_config, http).fetch()
            results.append(
                {
                    "feed": result.feed,
                    "provider": result.provider,
                    "raw_count": result.raw_count,
                    "desired_count": len(result.events),
                    "rejected_count": result.rejected_count,
                    "warnings": result.warnings,
                }
            )
    print(json.dumps({"sources": results}, indent=2))
    return 0


def vars_stat(stat: Any) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(stat)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    logger = configure_logging()
    try:
        config = load_config(args.config)
    except Exception as error:
        logger.error("config_validation_failed error=%s", error)
        return 2

    if args.command == "validate-config":
        logger.info("config_valid path=%s", Path(args.config).resolve())
        return 0
    if args.command == "source-smoke":
        try:
            return run_source_smoke(config, args.feed)
        except Exception:
            logger.exception("source_smoke_failed")
            return 1

    try:
        service = google_calendar_service()
        if args.command == "sync":
            return run_sync(config, args, logger, service)

        with JsonHttpClient() as http:
            runner = SyncRunner(config, service, logger, http)
            calendar_ids = runner.calendar_ids()
            gateway = GoogleCalendarGateway(service, config.timezone)
            if args.command == "migrate-v1":
                if args.confirm_rebuild != "DELETE_FUTURE_EVENTS":
                    raise ValueError("migration confirmation did not match DELETE_FUTURE_EVENTS")
                prepared = []
                if config.feeds.pokemon_go.enabled:
                    prepared.append(
                        PokemonSource(
                            config.feeds.pokemon_go,
                            config.timezone,
                            http,
                        ).fetch()
                    )
                if config.feeds.valorant.enabled:
                    prepared.append(ValorantSource(config.feeds.valorant, http).fetch())
                empty = [result.feed for result in prepared if not result.events]
                if empty:
                    raise ValueError(
                        "migration preflight refused empty desired feeds: " + ", ".join(empty)
                    )
                deleted = gateway.backup_and_clear_future(calendar_ids, args.backup)
                logger.info("migration_backup_complete deleted=%d path=%s", deleted, args.backup)
                results = [
                    gateway.reconcile(
                        calendar_id=calendar_ids[result.feed],
                        source=result,
                        safety=config.safety,
                    )
                    for result in prepared
                ]
                print(
                    json.dumps(
                        {"migration_results": [vars_stat(item) for item in results]}, indent=2
                    )
                )
                return 0
            if args.command == "restore-backup":
                if args.confirm_restore != "RESTORE_EVENTS":
                    raise ValueError("restore confirmation did not match RESTORE_EVENTS")
                restored = gateway.restore_backup(calendar_ids, args.backup)
                logger.info("backup_restore_complete restored=%d path=%s", restored, args.backup)
                return 0
    except Exception as error:
        logger.exception("command_failed command=%s", args.command)
        notify_discord(
            os.environ.get("DISCORD_WEBHOOK_URL"),
            f"Calendar sync command failed: {type(error).__name__}: {error}",
            logger,
        )
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
