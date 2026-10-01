"""Integration fixtures backed by a real PostgreSQL.

Resolution order:
1. TEST_DATABASE_URL (CI service container, or a local database you own).
2. A throwaway testcontainers PostgreSQL if Docker is available.
3. Otherwise integration tests are skipped (never silently "passed").

The database is migrated with Alembic, so these tests exercise the real
migration rather than metadata.create_all().
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "services" / "api" / "alembic.ini"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        # The fixture drops and recreates the schema. Refuse anything that does
        # not look like a dedicated test database.
        if "test" not in make_url(explicit).database.lower():  # type: ignore[union-attr]
            pytest.exit("TEST_DATABASE_URL database name must contain 'test'", returncode=2)
        yield explicit
        return
    try:
        from testcontainers.community.postgres import PostgresContainer  # noqa: PLC0415
    except ImportError:  # pragma: no cover
        pytest.skip("testcontainers not installed and TEST_DATABASE_URL not set")
    try:
        container = PostgresContainer("postgres:17-alpine", driver="asyncpg")
        container.start()
    except Exception as exc:  # Docker not available
        pytest.skip(f"No TEST_DATABASE_URL and Docker unavailable: {type(exc).__name__}")
    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    explicit = os.environ.get("TEST_REDIS_URL")
    if explicit:
        # Auth tests FLUSHDB between runs; never allow the default database 0.
        if urlparse(explicit).path.strip("/") in {"", "0"}:
            pytest.exit("TEST_REDIS_URL must select a non-zero database, e.g. /15", returncode=2)
        yield explicit
        return
    try:
        from testcontainers.community.redis import RedisContainer  # noqa: PLC0415

        container = RedisContainer("redis:7.4-alpine")
        container.start()
    except Exception as exc:
        pytest.skip(f"No TEST_REDIS_URL and Docker unavailable: {type(exc).__name__}")
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"
    finally:
        container.stop()


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> str:
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = database_url
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return database_url


@pytest.fixture
async def engine(migrated_database: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_database)
    try:
        yield engine
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Full application harness: real PostgreSQL + Redis, fake Google + fake Drive.
# ---------------------------------------------------------------------------

from typing import Any  # noqa: E402

import httpx  # noqa: E402
from drive_fake import FakeDrive  # noqa: E402  (services/api/tests on pythonpath)
from google_fake import CLIENT_ID, FakeGoogle  # noqa: E402

from saige_api.auth.google import GoogleOAuthClient  # noqa: E402
from saige_api.core.config import Environment, Settings  # noqa: E402
from saige_api.crypto import generate_key  # noqa: E402
from saige_api.main import create_app  # noqa: E402
from saige_api.resources import Resources  # noqa: E402

WEB = "http://web.test"
REDIRECT_URI = f"{WEB}/api/v1/auth/google/callback"
Harness = tuple[httpx.AsyncClient, FakeGoogle, FakeDrive]


@pytest.fixture
def make_client(migrated_database: str, redis_url: str) -> Any:
    async def _make(**overrides: Any) -> AsyncIterator[Harness]:
        values: dict[str, Any] = {
            "app_env": Environment.TEST,
            "log_json": False,
            "log_level": "WARNING",
            "database_url": migrated_database,
            "redis_url": redis_url,
            "jwt_secret": "j" * 48,
            "token_encryption_key": generate_key(),
            "web_public_url": WEB,
            "google_client_id": CLIENT_ID,
            "google_client_secret": "test-secret",
            "google_redirect_uri": REDIRECT_URI,
            "dev_login_enabled": True,
            "auth_rate_limit_per_minute": 1000,
        }
        values.update(overrides)
        settings = Settings(_env_file=None, **values)  # type: ignore[call-arg]
        google, drive = FakeGoogle(), FakeDrive()

        def factory(s: Settings) -> Resources:
            resources = Resources.create(s)
            resources.external_http = httpx.AsyncClient(transport=google.transport(drive))
            if s.google_oauth_configured:
                resources.google = GoogleOAuthClient(
                    client_id=CLIENT_ID,
                    client_secret="test-secret",
                    redirect_uri=REDIRECT_URI,
                    http=resources.external_http,
                )
            return resources

        app = create_app(settings, resource_factory=factory)
        async with app.router.lifespan_context(app):
            await app.state.resources.redis.flushdb()
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url=WEB) as client:
                yield client, google, drive

    return _make
