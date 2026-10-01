from __future__ import annotations

import asyncio

from support import ClientFactory, StaticCheck

from saige_api.health import CheckStatus, run_check


async def test_health_is_ok_without_dependencies(client_factory: ClientFactory) -> None:
    async for client in client_factory():
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "saige-api", "version": "0.1.0"}


async def test_ready_when_all_checks_pass(client_factory: ClientFactory) -> None:
    checks = [StaticCheck("database", critical=True), StaticCheck("qdrant", critical=False)]
    async for client in client_factory(checks):
        response = await client.get("/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert {c["name"]: c["status"] for c in body["checks"]} == {
            "database": "ok",
            "qdrant": "ok",
        }


async def test_degraded_when_non_critical_check_fails(client_factory: ClientFactory) -> None:
    checks = [
        StaticCheck("database", critical=True),
        StaticCheck("qdrant", critical=False, error=ConnectionError("boom")),
    ]
    async for client in client_factory(checks):
        response = await client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "degraded"


async def test_not_ready_when_critical_check_fails(client_factory: ClientFactory) -> None:
    checks = [StaticCheck("database", critical=True, error=ConnectionError("refused"))]
    async for client in client_factory(checks):
        response = await client.get("/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"


async def test_failure_detail_does_not_leak_driver_messages(client_factory: ClientFactory) -> None:
    secret_message = "password authentication failed for user saige at db.internal:5432"
    checks = [StaticCheck("database", critical=True, error=OSError(secret_message))]
    async for client in client_factory(checks):
        response = await client.get("/ready")
        assert secret_message not in response.text
        assert response.json()["checks"][0]["detail"] == "OSError"


async def test_slow_check_times_out() -> None:
    class SlowCheck:
        name = "slow"
        critical = True

        async def check(self) -> str | None:
            await asyncio.sleep(5)
            return None

    result = await run_check(SlowCheck(), timeout_seconds=0.05)
    assert result.status is CheckStatus.FAIL
    assert result.detail == "timeout"
