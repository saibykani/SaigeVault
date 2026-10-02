"""Fixed-window rate limiting over the shared key-value store."""

from __future__ import annotations

import time

from saige_api.core.errors import RateLimitedError
from saige_api.kv import KeyValueStore


class RateLimiter:
    def __init__(self, store: KeyValueStore) -> None:
        self._store = store

    async def hit(self, bucket: str, key: str, *, limit: int, window_seconds: int = 60) -> None:
        """Raise RateLimitedError once `limit` hits occur within the window."""
        window = int(time.time()) // window_seconds
        count = await self._store.incr(
            f"saige:ratelimit:{bucket}:{key}:{window}", ttl_seconds=window_seconds + 1
        )
        if count > limit:
            raise RateLimitedError("Too many requests. Please wait a minute and try again.")
