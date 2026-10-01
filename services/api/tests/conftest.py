from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from support import ClientFactory, StubResources, make_settings

from saige_api.health import HealthCheck
from saige_api.main import create_app


@pytest.fixture
def client_factory() -> ClientFactory:
    """Builds an httpx client bound to an app whose dependencies are stubbed."""

    async def _make(
        checks: list[HealthCheck] | None = None, **settings_overrides: Any
    ) -> AsyncIterator[httpx.AsyncClient]:
        settings = make_settings(**settings_overrides)
        resources = StubResources(settings=settings, health_checks=checks or [])
        app = create_app(settings, resource_factory=lambda _s: resources)  # type: ignore[arg-type,return-value]
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                yield client

    return _make
