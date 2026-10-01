"""Google Drive connection lifecycle on real PostgreSQL + Redis (fake Google/Drive)."""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from drive_fake import FakeDrive
from google_fake import FakeGoogle
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

WEB = "http://web.test"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def csrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("saige_csrf", "")}


async def sign_in(client: httpx.AsyncClient, email: str | None = None) -> str:
    email = email or f"drive-{uuid.uuid4().hex[:8]}@example.com"
    response = await client.post("/api/v1/auth/dev-login", json={"email": email})
    assert response.status_code == 200, response.text
    return email


async def start_connect(client: httpx.AsyncClient) -> dict[str, list[str]]:
    response = await client.get("/api/v1/storage/google-drive/connect")
    assert response.status_code == 302, response.text
    assert response.headers["location"].startswith("https://accounts.google.com/")
    return parse_qs(urlparse(response.headers["location"]).query)


async def finish_connect(
    client: httpx.AsyncClient, google: FakeGoogle, query: dict[str, list[str]]
) -> httpx.Response:
    code = uuid.uuid4().hex
    google.codes[code] = query["nonce"][0]
    return await client.get(
        "/api/v1/auth/google/callback", params={"code": code, "state": query["state"][0]}
    )


def grant_drive(google: FakeGoogle, *, sub: str | None = None) -> None:
    google.granted_scope = f"openid email {DRIVE_SCOPE}"
    google.issue_refresh_token = True
    google.identity["sub"] = sub or f"drive-sub-{uuid.uuid4().hex}"


async def connect(client: httpx.AsyncClient, google: FakeGoogle) -> dict[str, Any]:
    grant_drive(google)
    response = await finish_connect(client, google, await start_connect(client))
    assert response.headers["location"] == f"{WEB}/settings?drive=connected#storage"
    connections = (await client.get("/api/v1/storage/connections")).json()["connections"]
    assert len(connections) == 1
    return connections[0]  # type: ignore[no-any-return]


async def test_connect_requests_least_privilege_offline_access(make_client: Any) -> None:
    async for client, _google, _drive in make_client():
        email = await sign_in(client)
        query = await start_connect(client)
        assert query["scope"] == [f"openid email {DRIVE_SCOPE}"]
        assert query["access_type"] == ["offline"]
        assert query["prompt"] == ["consent"]
        assert query["code_challenge_method"] == ["S256"]
        assert query["login_hint"] == [email]


async def test_connect_stores_only_encrypted_tokens(make_client: Any, engine: AsyncEngine) -> None:
    async for client, google, drive in make_client():
        await sign_in(client)
        conn = await connect(client, google)
        assert conn["status"] == "active"
        assert conn["account_email"] == google.identity["email"]
        assert DRIVE_SCOPE in conn["scopes"]
        assert "token" not in str(conn).lower()

        roots = [f for f in drive.files.values() if f.app_properties.get("saigeVault") == "root"]
        assert len(roots) == 1 and roots[0].name == "Saige Vault"

        async with engine.connect() as db:
            row = (
                await db.execute(
                    text(
                        "SELECT encrypted_access_token, encrypted_refresh_token, root_folder_id, "
                        "changes_page_token FROM storage_connections WHERE id = :id"
                    ),
                    {"id": conn["id"]},
                )
            ).one()
            audits = await db.scalar(
                text(
                    "SELECT count(*) FROM audit_logs WHERE action = 'OAUTH_CONNECT' "
                    "AND outcome = 'success' AND resource_id = :id"
                ),
                {"id": conn["id"]},
            )
        refresh_token = next(iter(google.refresh_tokens))
        assert refresh_token.encode() not in row.encrypted_refresh_token
        assert google.access_token.encode() not in row.encrypted_access_token
        assert row.root_folder_id == roots[0].id
        assert row.changes_page_token is not None
        assert audits == 1


async def test_quota_is_read_through_the_connection(make_client: Any) -> None:
    async for client, google, _drive in make_client():
        await sign_in(client)
        conn = await connect(client, google)
        quota = (await client.get(f"/api/v1/storage/connections/{conn['id']}/quota")).json()
        assert quota["limit_bytes"] == 16106127360
        assert quota["usage_bytes"] == 1048576


@pytest.mark.parametrize(
    ("setup", "error"),
    [
        (lambda g: setattr(g, "granted_scope", "openid email"), "drive_scope_not_granted"),
        (lambda g: setattr(g, "issue_refresh_token", False), "drive_offline_access_missing"),
    ],
)
async def test_incomplete_consent_is_rejected(make_client: Any, setup: Any, error: str) -> None:
    async for client, google, _drive in make_client():
        await sign_in(client)
        grant_drive(google)
        setup(google)
        response = await finish_connect(client, google, await start_connect(client))
        assert response.headers["location"] == f"{WEB}/settings?drive_error={error}#storage"
        assert (await client.get("/api/v1/storage/connections")).json()["connections"] == []


async def test_consent_cannot_be_completed_by_another_account(make_client: Any) -> None:
    async for client, google, _drive in make_client():
        await sign_in(client)
        query = await start_connect(client)
        # Victim signs out; attacker's session completes the victim's consent.
        await client.post("/api/v1/auth/logout", headers=csrf(client))
        await sign_in(client)
        grant_drive(google)
        response = await finish_connect(client, google, query)
        assert "drive_error=account_mismatch" in response.headers["location"]
        assert (await client.get("/api/v1/storage/connections")).json()["connections"] == []


async def test_connect_requires_sign_in(make_client: Any) -> None:
    async for client, _google, _drive in make_client():
        assert (await client.get("/api/v1/storage/google-drive/connect")).status_code == 401


async def test_disconnect_revokes_and_wipes_tokens(make_client: Any, engine: AsyncEngine) -> None:
    async for client, google, _drive in make_client():
        await sign_in(client)
        conn = await connect(client, google)
        refresh_token = next(iter(google.refresh_tokens))

        response = await client.post(
            f"/api/v1/storage/connections/{conn['id']}/disconnect", headers=csrf(client)
        )
        assert response.status_code == 200
        assert response.json() == {"revoked_at_provider": True}
        assert google.revoked == [refresh_token]

        async with engine.connect() as db:
            row = (
                await db.execute(
                    text(
                        "SELECT status, encrypted_access_token, encrypted_refresh_token "
                        "FROM storage_connections WHERE id = :id"
                    ),
                    {"id": conn["id"]},
                )
            ).one()
        assert row.status == "disconnected"
        assert row.encrypted_access_token is None and row.encrypted_refresh_token is None

        quota = await client.get(f"/api/v1/storage/connections/{conn['id']}/quota")
        assert quota.status_code == 404
        again = await client.post(
            f"/api/v1/storage/connections/{conn['id']}/disconnect", headers=csrf(client)
        )
        assert again.status_code == 404


async def test_disconnect_requires_csrf(make_client: Any) -> None:
    async for client, google, _drive in make_client():
        await sign_in(client)
        conn = await connect(client, google)
        response = await client.post(f"/api/v1/storage/connections/{conn['id']}/disconnect")
        assert response.status_code == 403


async def test_other_users_connections_are_invisible(make_client: Any) -> None:
    async for client, google, _drive in make_client():
        await sign_in(client)
        conn = await connect(client, google)

        intruder = httpx.AsyncClient(transport=client._transport, base_url=WEB)
        await sign_in(intruder)
        assert (await intruder.get("/api/v1/storage/connections")).json()["connections"] == []
        quota = await intruder.get(f"/api/v1/storage/connections/{conn['id']}/quota")
        assert quota.status_code == 404
        disconnect = await intruder.post(
            f"/api/v1/storage/connections/{conn['id']}/disconnect", headers=csrf(intruder)
        )
        assert disconnect.status_code == 404
        await intruder.aclose()
        # The owner's connection is untouched.
        assert (await client.get("/api/v1/storage/connections")).json()["connections"][0][
            "status"
        ] == "active"


async def test_expired_access_token_is_refreshed_then_revocation_needs_reconnect(
    make_client: Any, engine: AsyncEngine
) -> None:
    async for client, google, drive in make_client():
        await sign_in(client)
        conn = await connect(client, google)

        async def expire(connection_id: str = conn["id"]) -> None:
            async with engine.begin() as db:
                await db.execute(
                    text(
                        "UPDATE storage_connections SET access_token_expires_at = now() - "
                        "interval '1 hour' WHERE id = :id"
                    ),
                    {"id": connection_id},
                )

        # 1. Expired access token: refreshed transparently with the stored refresh token.
        await expire()
        google.access_token = "drive-access-2"
        drive.valid_tokens = {"drive-access-2"}
        quota = await client.get(f"/api/v1/storage/connections/{conn['id']}/quota")
        assert quota.status_code == 200
        assert any(r.get("grant_type") == ["refresh_token"] for r in google.token_requests)

        # 2. The user revokes Saige in their Google account: reconnect required.
        await expire()
        google.refresh_tokens.clear()
        quota = await client.get(f"/api/v1/storage/connections/{conn['id']}/quota")
        assert quota.status_code == 409
        assert quota.json()["error"]["code"] == "storage_reauth_required"
        listed = (await client.get("/api/v1/storage/connections")).json()["connections"]
        assert listed[0]["status"] == "needs_reauth"


async def test_drive_unavailable_without_encryption_key(make_client: Any) -> None:
    async for client, _google, _drive in make_client(token_encryption_key=None):
        await sign_in(client)
        info = (await client.get("/api/v1/system/info")).json()
        assert info["google_drive_available"] is False
        response = await client.get("/api/v1/storage/google-drive/connect")
        assert response.status_code == 503


async def test_fake_drive_is_isolated_per_test(make_client: Any) -> None:
    async for _client, _google, drive in make_client():
        assert isinstance(drive, FakeDrive)
        assert drive.files == {}
