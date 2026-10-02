"""Process-wide resources (DB engine, Redis, HTTP clients, auth services)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import timedelta

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from saige_api.auth.google import GoogleOAuthClient
from saige_api.auth.state import OAuthStateStore
from saige_api.auth.tokens import TokenService
from saige_api.core.config import Settings
from saige_api.core.logging import get_logger
from saige_api.crypto import TokenCipher
from saige_api.db.session import create_engine, create_session_factory
from saige_api.health import (
    DatabaseCheck,
    HealthCheck,
    QdrantCheck,
    RedisCheck,
    WorkerHeartbeatCheck,
)
from saige_api.kv import KeyValueStore, MemoryStore, RedisStore
from saige_api.ratelimit import RateLimiter

logger = get_logger("saige_api.resources")


def _signing_key(settings: Settings) -> str:
    if settings.jwt_secret is not None:
        return settings.jwt_secret.get_secret_value()
    # Production refuses to start without JWT_SECRET (see Settings). Locally an
    # ephemeral key is acceptable: sessions simply end when the API restarts.
    logger.warning("jwt_secret_ephemeral", reason="JWT_SECRET not set; sessions reset on restart")
    return secrets.token_urlsafe(48)


@dataclass
class Resources:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis | None
    kv: KeyValueStore
    # Separate clients: the Qdrant client carries the Qdrant API key and must
    # never be used for third-party calls.
    qdrant_http: httpx.AsyncClient
    external_http: httpx.AsyncClient
    tokens: TokenService
    oauth_state: OAuthStateStore
    rate_limiter: RateLimiter
    google: GoogleOAuthClient | None = None
    # None when TOKEN_ENCRYPTION_KEY is unset: storage connections are then unavailable.
    cipher: TokenCipher | None = None
    health_checks: list[HealthCheck] = field(default_factory=list)

    @classmethod
    def create(cls, settings: Settings) -> Resources:
        engine = create_engine(settings)
        redis = (
            Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=5)
            if settings.redis_url
            else None
        )
        if redis is None:
            logger.warning("redis_disabled", reason="REDIS_URL not set; using in-process state")
        kv: KeyValueStore = RedisStore(redis) if redis is not None else MemoryStore()
        qdrant_headers = (
            {"api-key": settings.qdrant_api_key.get_secret_value()}
            if settings.qdrant_api_key
            else {}
        )
        qdrant_http = httpx.AsyncClient(timeout=httpx.Timeout(5.0), headers=qdrant_headers)
        external_http = httpx.AsyncClient(timeout=httpx.Timeout(10.0), follow_redirects=False)
        google = None
        if settings.google_oauth_configured:
            assert settings.google_client_secret is not None  # noqa: S101 - narrowed by property
            google = GoogleOAuthClient(
                client_id=settings.google_client_id or "",
                client_secret=settings.google_client_secret.get_secret_value(),
                redirect_uri=settings.google_redirect_uri or "",
                http=external_http,
            )
        resources = cls(
            settings=settings,
            engine=engine,
            session_factory=create_session_factory(engine),
            redis=redis,
            kv=kv,
            qdrant_http=qdrant_http,
            external_http=external_http,
            tokens=TokenService(_signing_key(settings), settings.access_token_ttl_seconds),
            oauth_state=OAuthStateStore(kv),
            rate_limiter=RateLimiter(kv),
            google=google,
            cipher=(
                TokenCipher.from_single_key(settings.token_encryption_key.get_secret_value())
                if settings.token_encryption_key
                else None
            ),
        )
        checks: list[HealthCheck] = [DatabaseCheck(engine)]
        if redis is not None:
            checks += [
                RedisCheck(redis),
                WorkerHeartbeatCheck(redis, settings.worker_heartbeat_max_age_seconds),
            ]
        checks.append(QdrantCheck(qdrant_http, settings.qdrant_url))
        resources.health_checks = checks
        return resources

    @property
    def refresh_ttl(self) -> timedelta:
        return timedelta(days=self.settings.refresh_token_ttl_days)

    async def aclose(self) -> None:
        await self.qdrant_http.aclose()
        await self.external_http.aclose()
        if self.redis is not None:
            await self.redis.aclose()
        await self.engine.dispose()
