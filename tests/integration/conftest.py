"""Integration fixtures backed by a real MongoDB (and Redis when available).

Resolution order for MongoDB:
1. TEST_MONGODB_URL (CI service container, or a local server you own).
2. A throwaway testcontainers MongoDB if Docker is available.
3. Otherwise integration tests are skipped (never silently "passed").

File content goes to an in-memory object store standing in for Cloudflare R2.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from typing import Any
from urllib.parse import urlparse

import httpx
import pytest
from google_fake import CLIENT_ID, FakeGoogle  # services/api/tests on pythonpath
from pymongo.asynchronous.database import AsyncDatabase

from saige_api.auth.google import GoogleOAuthClient
from saige_api.core.config import Environment, Settings
from saige_api.crypto import generate_key
from saige_api.db import create_client
from saige_api.main import create_app
from saige_api.resources import Resources
from saige_api.storage.objects import MemoryObjectStore

TEST_DB = "saige_test"


@pytest.fixture(scope="session")
def mongodb_url() -> Iterator[str]:
    explicit = os.environ.get("TEST_MONGODB_URL")
    if explicit:
        yield explicit
        return
    try:
        from testcontainers.mongodb import MongoDbContainer  # noqa: PLC0415
    except ImportError:  # pragma: no cover
        pytest.skip("testcontainers not installed and TEST_MONGODB_URL not set")
    try:
        container = MongoDbContainer("mongo:8.0")
        container.start()
    except Exception as exc:  # Docker not available
        pytest.skip(f"No TEST_MONGODB_URL and Docker unavailable: {type(exc).__name__}")
    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@pytest.fixture(scope="session")
def mongodb_uri(mongodb_url: str) -> str:
    """URI pointing at the dedicated test database (dropped once per session)."""
    parsed = urlparse(mongodb_url)
    query = parsed.query
    if parsed.username and "authSource" not in query:
        query = "&".join(filter(None, [query, "authSource=admin"]))
    uri = parsed._replace(path=f"/{TEST_DB}", query=query).geturl()
    import pymongo  # noqa: PLC0415

    client: pymongo.MongoClient[dict[str, Any]] = pymongo.MongoClient(uri)
    client.drop_database(TEST_DB)
    client.close()
    return uri


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str | None]:
    explicit = os.environ.get("TEST_REDIS_URL")
    if explicit:
        # Auth tests FLUSHDB between runs; never allow the default database 0.
        if urlparse(explicit).path.strip("/") in {"", "0"}:
            pytest.exit("TEST_REDIS_URL must select a non-zero database, e.g. /15", returncode=2)
        yield explicit
        return
    yield None  # in-process state (single instance), which the app supports


@pytest.fixture
async def db(mongodb_uri: str) -> AsyncIterator[AsyncDatabase[dict[str, Any]]]:
    client = create_client(mongodb_uri)
    try:
        yield client[TEST_DB]
    finally:
        await client.close()


WEB = "http://web.test"
REDIRECT_URI = f"{WEB}/api/v1/auth/google/callback"
Harness = tuple[httpx.AsyncClient, FakeGoogle, MemoryObjectStore]


@pytest.fixture
def make_client(mongodb_uri: str, redis_url: str | None) -> Any:
    async def _make(**overrides: Any) -> AsyncIterator[Harness]:
        values: dict[str, Any] = {
            "app_env": Environment.TEST,
            "log_json": False,
            "log_level": "WARNING",
            "mongodb_uri": mongodb_uri,
            "redis_url": redis_url,
            "jwt_secret": "j" * 48,
            "token_encryption_key": generate_key(),
            "web_public_url": WEB,
            "google_client_id": CLIENT_ID,
            "google_client_secret": "test-secret",
            "google_redirect_uri": REDIRECT_URI,
            "dev_login_enabled": True,
            "auth_rate_limit_per_minute": 1000,
            "password_breach_check": False,  # no network in tests
        }
        storage = overrides.pop("storage", True)
        values.update(overrides)
        settings = Settings(_env_file=None, **values)  # type: ignore[call-arg]
        google, objects = FakeGoogle(), MemoryObjectStore()

        def factory(s: Settings) -> Resources:
            resources = Resources.create(s)
            resources.objects = objects if storage else None
            resources.external_http = httpx.AsyncClient(transport=google.transport())
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
            if app.state.resources.redis is not None:
                await app.state.resources.redis.flushdb()
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url=WEB) as client:
                yield client, google, objects

    return _make
