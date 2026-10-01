"""Shared test doubles for API unit tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from saige_api.core.config import Environment, Settings
from saige_api.health import HealthCheck

TEST_KEY = "A" * 43 + "="  # 32 zero bytes; valid url-safe base64 key for tests


class StaticCheck:
    """Health check with a predetermined outcome."""

    def __init__(self, name: str, *, critical: bool, error: Exception | None = None) -> None:
        self.name = name
        self.critical = critical
        self._error = error

    async def check(self) -> str | None:
        if self._error is not None:
            raise self._error
        return None


@dataclass
class StubResources:
    settings: Settings
    health_checks: list[HealthCheck] = field(default_factory=list)
    closed: bool = False

    async def aclose(self) -> None:
        self.closed = True


def make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {"app_env": Environment.TEST, "log_json": False, "log_level": "WARNING"}
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


ClientFactory = Callable[..., Any]
