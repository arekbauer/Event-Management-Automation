from __future__ import annotations

import logging

import httpx


def notify_discord(webhook_url: str | None, message: str, logger: logging.Logger) -> None:
    if not webhook_url:
        logger.warning("Discord webhook is not configured; alert was not delivered")
        return
    try:
        response = httpx.post(
            webhook_url,
            json={
                "content": message,
                "embeds": [
                    {"title": "Calendar Sync v2", "description": message, "color": 16711680}
                ],
            },
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Could not deliver Discord alert")
