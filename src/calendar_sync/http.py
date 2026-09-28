from __future__ import annotations

import random
import time
from collections.abc import Mapping
from typing import Any

import httpx


class SourceRequestError(RuntimeError):
    pass


class JsonHttpClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 15,
        attempts: int = 3,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.attempts = attempts
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            transport=transport,
            headers={"User-Agent": "calendar-sync/2"},
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> JsonHttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                response = self.client.get(url, params=params, headers=headers)
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                if 400 <= response.status_code < 500:
                    raise SourceRequestError(
                        f"non-retryable response {response.status_code} from {url}"
                    )
                return response.json()
            except SourceRequestError:
                raise
            except (httpx.TransportError, httpx.HTTPStatusError) as error:
                last_error = error
                if attempt < self.attempts:
                    time.sleep((2 ** (attempt - 1)) + random.uniform(0, 0.25))
            except ValueError as error:
                raise SourceRequestError(f"invalid JSON from {url}") from error
        raise SourceRequestError(
            f"request failed after {self.attempts} attempts: {url}"
        ) from last_error
