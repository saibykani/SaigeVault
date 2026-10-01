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
