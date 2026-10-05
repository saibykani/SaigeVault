"""Small key-value interface for short-lived state (OAuth state, rate limits).

Redis is used when REDIS_URL is set. Otherwise an in-process store is used,
which is correct for a single API instance (e.g. one free-tier container) but
must not be used when running several API replicas.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable
from typing import Protocol, cast

from redis.asyncio import Redis


class KeyValueStore(Protocol):
    @property
    def shared(self) -> bool:
        """True when state is shared across processes (Redis)."""
        ...

    async def set(self, key: str, value: str, *, ttl_seconds: int) -> None: ...
    async def get(self, key: str) -> str | None: ...
    async def pop(self, key: str) -> str | None: ...
    async def incr(self, key: str, *, ttl_seconds: int) -> int: ...


class RedisStore:
    shared = True

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        await self._redis.set(key, value, ex=ttl_seconds)

    async def get(self, key: str) -> str | None:
        raw = await cast(Awaitable[bytes | str | None], self._redis.get(key))
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else raw

    async def pop(self, key: str) -> str | None:
        raw = await cast(Awaitable[bytes | str | None], self._redis.getdel(key))
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else raw

    async def incr(self, key: str, *, ttl_seconds: int) -> int:
        count = await cast(Awaitable[int], self._redis.incr(key))
        if count == 1:
            await self._redis.expire(key, ttl_seconds)
        return count


class Clock(Protocol):
    def monotonic(self) -> float: ...


class MemoryStore:
    """In-process store with expiry. Single-instance deployments only."""

    shared = False
    MAX_KEYS = 50_000

    def __init__(self, clock: Clock | None = None) -> None:
        self._data: dict[str, tuple[str, float]] = {}
        self._now = clock.monotonic if clock is not None else time.monotonic

    def _purge(self) -> None:
        now = self._now()
        expired = [k for k, (_, exp) in self._data.items() if exp <= now]
        for k in expired:
            del self._data[k]
        # Bound memory even under abuse: drop the oldest-expiring keys.
        if len(self._data) > self.MAX_KEYS:
            for k, _ in sorted(self._data.items(), key=lambda kv: kv[1][1])[
                : len(self._data) - self.MAX_KEYS
            ]:
                del self._data[k]

    def _live(self, key: str) -> tuple[str, float] | None:
        entry = self._data.get(key)
        if entry is None or entry[1] <= self._now():
            self._data.pop(key, None)
            return None
        return entry

    async def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        self._purge()
        self._data[key] = (value, self._now() + ttl_seconds)

    async def get(self, key: str) -> str | None:
        entry = self._live(key)
        return entry[0] if entry else None

    async def pop(self, key: str) -> str | None:
        entry = self._live(key)
        self._data.pop(key, None)
        return entry[0] if entry else None

    async def incr(self, key: str, *, ttl_seconds: int) -> int:
        entry = self._live(key)
        if entry is None:
            self._purge()
            self._data[key] = ("1", self._now() + ttl_seconds)
            return 1
        count = int(entry[0]) + 1
        self._data[key] = (str(count), entry[1])
        return count
