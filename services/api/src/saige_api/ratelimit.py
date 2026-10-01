"""Fixed-window rate limiting backed by Redis."""

from __future__ import annotations

import time
from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis

from saige_api.core.errors import RateLimitedError


class RateLimiter:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def hit(self, bucket: str, key: str, *, limit: int, window_seconds: int = 60) -> None:
        """Raise RateLimitedError once `limit` hits occur within the window."""
        window = int(time.time()) // window_seconds
        redis_key = f"saige:ratelimit:{bucket}:{key}:{window}"
        count = await cast(Awaitable[int], self._redis.incr(redis_key))
        if count == 1:
            await self._redis.expire(redis_key, window_seconds + 1)
        if count > limit:
            raise RateLimitedError("Too many requests. Please wait a minute and try again.")
