"""SAQ worker entrypoint.

Run with:  saq saige_worker.main.settings   (or the `saige-worker` script)

Job functions are registered phase by phase (document processing in
Phase 7, Drive sync in Phase 13). Today the worker publishes a heartbeat
that the API's /ready endpoint reports on.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from saq import CronJob, Queue

from saige_api.core.config import get_settings
from saige_api.core.logging import configure_logging, get_logger
from saige_api.health import WORKER_HEARTBEAT_KEY
from saige_worker import __version__

logger = get_logger("saige_worker")

QUEUE_NAME = "saige"
HEARTBEAT_TTL_SECONDS = 120


async def publish_heartbeat(redis: Redis) -> None:
    await redis.set(WORKER_HEARTBEAT_KEY, datetime.now(UTC).isoformat(), ex=HEARTBEAT_TTL_SECONDS)


async def heartbeat(ctx: dict[str, Any]) -> None:
    await publish_heartbeat(ctx["redis"])


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.log_json)
    if not settings.redis_url:
        raise RuntimeError("The worker requires REDIS_URL (its job queue lives in Redis).")
    ctx["redis"] = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
    await publish_heartbeat(ctx["redis"])
    logger.info("worker_startup", version=__version__, environment=settings.app_env.value)


async def shutdown(ctx: dict[str, Any]) -> None:
    redis: Redis | None = ctx.get("redis")
    if redis is not None:
        await redis.aclose()
    logger.info("worker_shutdown")


def build_settings() -> dict[str, Any]:
    queue = Queue.from_url(get_settings().redis_url or "redis://localhost:6379/0", name=QUEUE_NAME)
    return {
        "queue": queue,
        "functions": [],
        "concurrency": 4,
        # Six-field cron: the last field is seconds.
        "cron_jobs": [CronJob(heartbeat, cron="* * * * * */15", timeout=10, retries=1)],
        "startup": startup,
        "shutdown": shutdown,
    }


settings = build_settings()


def run() -> None:
    from saq.worker import start  # noqa: PLC0415

    start("saige_worker.main.settings")
