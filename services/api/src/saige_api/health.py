"""Dependency health checks used by the /ready endpoint.

Critical checks (PostgreSQL, Redis) gate readiness. Non-critical checks
(Qdrant, worker heartbeat) only degrade it: file management keeps working
while AI features are unavailable.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, cast

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

WORKER_HEARTBEAT_KEY = "saige:worker:heartbeat"


class HealthCheckFailedError(RuntimeError):
    """Failure with a message we wrote ourselves and know is safe to expose."""


class CheckStatus(StrEnum):
    OK = "ok"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: CheckStatus
    critical: bool
    latency_ms: float
    # Short, non-sensitive reason (exception class or fixed message).
    detail: str | None = None


class HealthCheck(Protocol):
    name: str
    critical: bool

    async def check(self) -> str | None:
        """Raise on failure. May return an informational detail string."""
        ...


class DatabaseCheck:
    name = "database"
    critical = True

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def check(self) -> str | None:
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            revision = await conn.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
        return f"schema={revision}" if revision else "schema=unmigrated"


class RedisCheck:
    name = "redis"
    critical = True

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def check(self) -> str | None:
        await cast(Awaitable[bool], self._redis.ping())
        return None


class QdrantCheck:
    name = "qdrant"
    critical = False

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._url = base_url.rstrip("/") + "/readyz"

    async def check(self) -> str | None:
        response = await self._client.get(self._url)
        response.raise_for_status()
        return None


class WorkerHeartbeatCheck:
    name = "worker"
    critical = False

    def __init__(self, redis: Redis, max_age_seconds: int) -> None:
        self._redis = redis
        self._max_age = max_age_seconds

    async def check(self) -> str | None:
        raw = await self._redis.get(WORKER_HEARTBEAT_KEY)
        if raw is None:
            raise HealthCheckFailedError("no worker heartbeat")
        beat = datetime.fromisoformat(raw.decode() if isinstance(raw, bytes) else str(raw))
        age = (datetime.now(UTC) - beat).total_seconds()
        if age > self._max_age:
            raise HealthCheckFailedError(f"heartbeat stale ({int(age)}s)")
        return f"heartbeat_age={int(age)}s"


async def run_check(check: HealthCheck, timeout_seconds: float) -> CheckResult:
    started = time.perf_counter()
    try:
        detail = await asyncio.wait_for(check.check(), timeout=timeout_seconds)
        status = CheckStatus.OK
    except TimeoutError:
        detail, status = "timeout", CheckStatus.FAIL
    except Exception as exc:
        # Expose only our own fixed messages, never driver error strings,
        # which can include hostnames or credentials.
        detail = str(exc) if isinstance(exc, HealthCheckFailedError) else type(exc).__name__
        status = CheckStatus.FAIL
    return CheckResult(
        name=check.name,
        status=status,
        critical=check.critical,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        detail=detail,
    )


async def run_checks(checks: list[HealthCheck], timeout_seconds: float) -> list[CheckResult]:
    return list(await asyncio.gather(*(run_check(c, timeout_seconds) for c in checks)))
