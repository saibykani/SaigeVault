"""Process-wide resources (DB engine, Redis, HTTP client) owned by the app lifespan."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from saige_api.core.config import Settings
from saige_api.db.session import create_engine, create_session_factory
from saige_api.health import (
    DatabaseCheck,
    HealthCheck,
    QdrantCheck,
    RedisCheck,
    WorkerHeartbeatCheck,
)


@dataclass
class Resources:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis
    http: httpx.AsyncClient
    health_checks: list[HealthCheck] = field(default_factory=list)

    @classmethod
    def create(cls, settings: Settings) -> Resources:
        engine = create_engine(settings)
        redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=5)
        headers = (
            {"api-key": settings.qdrant_api_key.get_secret_value()}
            if settings.qdrant_api_key
            else {}
        )
        http = httpx.AsyncClient(timeout=httpx.Timeout(5.0), headers=headers)
        resources = cls(
            settings=settings,
            engine=engine,
            session_factory=create_session_factory(engine),
            redis=redis,
            http=http,
        )
        resources.health_checks = [
            DatabaseCheck(engine),
            RedisCheck(redis),
            QdrantCheck(http, settings.qdrant_url),
            WorkerHeartbeatCheck(redis, settings.worker_heartbeat_max_age_seconds),
        ]
        return resources

    async def aclose(self) -> None:
        await self.http.aclose()
        await self.redis.aclose()
        await self.engine.dispose()
