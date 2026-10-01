from __future__ import annotations

from support import TEST_KEY, ClientFactory


async def test_security_headers_present(client_factory: ClientFactory) -> None:
    async for client in client_factory():
        response = await client.get("/health")
        headers = response.headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert headers["referrer-policy"] == "no-referrer"
        assert "default-src 'none'" in headers["content-security-policy"]
        assert headers["cache-control"] == "no-store"
        # HSTS only in production (local dev is plain HTTP).
        assert "strict-transport-security" not in headers


async def test_request_id_generated_and_echoed(client_factory: ClientFactory) -> None:
    async for client in client_factory():
        generated = await client.get("/health")
        assert len(generated.headers["x-request-id"]) == 32

        echoed = await client.get("/health", headers={"X-Request-ID": "client-req-12345"})
        assert echoed.headers["x-request-id"] == "client-req-12345"


async def test_malformed_request_id_is_replaced(client_factory: ClientFactory) -> None:
    async for client in client_factory():
        response = await client.get("/health", headers={"X-Request-ID": "bad id\nInjected: x"})
        assert response.headers["x-request-id"] != "bad id\nInjected: x"
        assert len(response.headers["x-request-id"]) == 32


async def test_not_found_uses_error_envelope(client_factory: ClientFactory) -> None:
    async for client in client_factory():
        response = await client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "not_found"
        assert body["error"]["request_id"] == response.headers["x-request-id"]


async def test_cors_allows_only_configured_origins(client_factory: ClientFactory) -> None:
    async for client in client_factory(cors_allowed_origins=["http://localhost:3000"]):
        allowed = await client.options(
            "/health",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
        assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"

        denied = await client.options(
            "/health",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" not in denied.headers


async def test_docs_disabled_in_production(client_factory: ClientFactory) -> None:
    async for client in client_factory(
        app_env="production",
        jwt_secret="x" * 48,
        token_encryption_key=TEST_KEY,
    ):
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/openapi.json")).status_code == 404
        assert "strict-transport-security" in (await client.get("/health")).headers


async def test_system_info_exposes_no_secrets(client_factory: ClientFactory) -> None:
    async for client in client_factory(
        google_client_id="client-id",
        google_client_secret="super-secret-value",
        google_redirect_uri="http://localhost:3000/api/v1/auth/google/callback",
    ):
        response = await client.get("/api/v1/system/info")
        assert response.status_code == 200
        assert response.json()["google_oauth_configured"] is True
        assert "super-secret-value" not in response.text
        assert "client-id" not in response.text
