"""End-to-end authentication against real PostgreSQL + Redis and a fake Google."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from google_fake import FakeGoogle  # services/api/tests (pytest pythonpath)
from pymongo.asynchronous.database import AsyncDatabase

from saige_api.auth import sessions as sessions_module

pytestmark = pytest.mark.integration

WEB = "http://web.test"  # matches the make_client harness in conftest.py


def csrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("saige_csrf", "")}


async def google_sign_in(
    client: httpx.AsyncClient, fake: FakeGoogle, *, next_path: str = "/files"
) -> httpx.Response:
    start = await client.get("/api/v1/auth/google/login", params={"next": next_path})
    assert start.status_code == 302
    query = parse_qs(urlparse(start.headers["location"]).query)
    code = uuid.uuid4().hex
    fake.codes[code] = query["nonce"][0]
    return await client.get(
        "/api/v1/auth/google/callback", params={"code": code, "state": query["state"][0]}
    )


async def dev_sign_in(client: httpx.AsyncClient, email: str | None = None) -> httpx.Response:
    email = email or f"dev-{uuid.uuid4().hex[:8]}@example.com"
    response = await client.post("/api/v1/auth/dev-login", json={"email": email})
    assert response.status_code == 200, response.text
    return response


async def test_google_sign_in_sets_secure_session(
    make_client: Any, db: AsyncDatabase[dict[str, Any]]
) -> None:
    async for client, fake, _drive in make_client():
        fake.identity["sub"] = f"sub-{uuid.uuid4().hex}"
        fake.identity["email"] = f"alice-{uuid.uuid4().hex[:6]}@example.com"
        response = await google_sign_in(client, fake)

        assert response.status_code == 302
        assert response.headers["location"] == f"{WEB}/files"
        set_cookies = response.headers.get_list("set-cookie")
        access = next(c for c in set_cookies if c.startswith("saige_access="))
        refresh = next(c for c in set_cookies if c.startswith("saige_refresh="))
        csrf_cookie = next(c for c in set_cookies if c.startswith("saige_csrf="))
        assert "HttpOnly" in access and "Path=/api" in access and "SameSite=lax" in access
        assert "HttpOnly" in refresh and "Path=/api/v1/auth" in refresh
        assert "HttpOnly" not in csrf_cookie
        # PKCE verifier was sent to the token endpoint.
        assert fake.token_requests[-1]["code_verifier"]

        session = await client.get("/api/v1/auth/session")
        assert session.status_code == 200
        assert session.json()["user"]["email"] == fake.identity["email"]

        user = await db.users.find_one({"email_lower": fake.identity["email"].lower()})
        assert user is not None
        logins = await db.audit_logs.count_documents(
            {"user_id": user["_id"], "action": "LOGIN", "outcome": "success"}
        )
        assert logins == 1


async def test_state_is_single_use(make_client: Any) -> None:
    async for client, fake, _drive in make_client():
        start = await client.get("/api/v1/auth/google/login")
        query = parse_qs(urlparse(start.headers["location"]).query)
        state, nonce = query["state"][0], query["nonce"][0]
        for code in ("c1", "c2"):
            fake.codes[code] = nonce
        first = await client.get(
            "/api/v1/auth/google/callback", params={"code": "c1", "state": state}
        )
        assert first.headers["location"] == f"{WEB}/"
        replay = await client.get(
            "/api/v1/auth/google/callback", params={"code": "c2", "state": state}
        )
        assert replay.headers["location"] == f"{WEB}/login?error=invalid_state"


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda f: setattr(f, "nonce_override", "attacker-nonce"), "nonce_mismatch"),
        (lambda f: f.identity.update(email_verified=False), "email_not_verified"),
    ],
)
async def test_rejected_identities_do_not_sign_in(
    make_client: Any, mutate: Callable[[FakeGoogle], None], error: str
) -> None:
    async for client, fake, _drive in make_client():
        mutate(fake)
        response = await google_sign_in(client, fake)
        assert response.headers["location"] == f"{WEB}/login?error={error}"
        assert "saige_access" not in client.cookies
        assert (await client.get("/api/v1/auth/session")).status_code == 401


async def test_open_redirect_is_neutralised(make_client: Any) -> None:
    async for client, fake, _drive in make_client():
        fake.identity["sub"] = f"sub-{uuid.uuid4().hex}"
        response = await google_sign_in(client, fake, next_path="//evil.example/steal")
        assert response.headers["location"] == f"{WEB}/"


async def test_refresh_rotates_and_detects_reuse(
    make_client: Any, monkeypatch: pytest.MonkeyPatch, db: AsyncDatabase[dict[str, Any]]
) -> None:
    monkeypatch.setattr(sessions_module, "ROTATION_GRACE", sessions_module.timedelta(0))
    async for client, _fake, _drive in make_client():
        await dev_sign_in(client)
        old_refresh = client.cookies.get("saige_refresh")

        rotated = await client.post("/api/v1/auth/refresh", headers=csrf(client))
        assert rotated.status_code == 200
        assert client.cookies.get("saige_refresh") != old_refresh
        session_id = rotated.json()["session_id"]

        # An attacker replays the stolen, already-rotated token.
        attacker = httpx.AsyncClient(transport=client._transport, base_url=WEB)
        attacker.cookies.set("saige_refresh", old_refresh or "", path="/api/v1/auth")
        attacker.cookies.set("saige_csrf", "x")
        replay = await attacker.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "x"})
        assert replay.status_code == 401
        await attacker.aclose()

        # The legitimate session is revoked as a precaution.
        assert (await client.get("/api/v1/auth/session")).status_code == 401
        events = await db.security_events.count_documents(
            {"event_type": "refresh_token_reuse", "details.session_id": session_id}
        )
        assert events == 1


async def test_csrf_required_for_cookie_mutations(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        await dev_sign_in(client)
        assert (await client.post("/api/v1/auth/refresh")).status_code == 403
        assert (await client.post("/api/v1/auth/logout")).status_code == 403
        wrong = {"X-CSRF-Token": "not-the-cookie"}
        assert (await client.post("/api/v1/auth/refresh", headers=wrong)).status_code == 403


async def test_logout_ends_session(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        await dev_sign_in(client)
        stale_access = client.cookies.get("saige_access")
        assert (await client.post("/api/v1/auth/logout", headers=csrf(client))).status_code == 204
        assert "saige_access" not in client.cookies
        # Even a captured access token stops working immediately.
        client.cookies.set("saige_access", stale_access or "", path="/api")
        assert (await client.get("/api/v1/auth/session")).status_code == 401


async def test_list_and_revoke_sessions(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        email = f"multi-{uuid.uuid4().hex[:6]}@example.com"
        other = httpx.AsyncClient(transport=client._transport, base_url=WEB)
        await dev_sign_in(other, email)
        await dev_sign_in(client, email)

        listed = (await client.get("/api/v1/auth/sessions")).json()["sessions"]
        assert len(listed) == 2
        other_id = next(s["id"] for s in listed if not s["current"])

        revoked = await client.delete(f"/api/v1/auth/sessions/{other_id}", headers=csrf(client))
        assert revoked.status_code == 204
        assert (await other.get("/api/v1/auth/session")).status_code == 401
        assert (await client.get("/api/v1/auth/session")).status_code == 200
        await other.aclose()


async def test_cannot_revoke_another_users_session(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        victim = httpx.AsyncClient(transport=client._transport, base_url=WEB)
        victim_session = (await dev_sign_in(victim)).json()["session_id"]
        await dev_sign_in(client)

        response = await client.delete(
            f"/api/v1/auth/sessions/{victim_session}", headers=csrf(client)
        )
        assert response.status_code == 404
        assert (await victim.get("/api/v1/auth/session")).status_code == 200
        await victim.aclose()


async def test_bearer_tokens_for_api_clients(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        await dev_sign_in(client)
        refresh_token = client.cookies.get("saige_refresh")
        api = httpx.AsyncClient(transport=client._transport, base_url=WEB)
        body = (
            await api.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        ).json()
        tokens = body["tokens"]
        assert tokens["token_type"] == "bearer"
        bearer = {"Authorization": f"Bearer {tokens['access_token']}"}
        assert (await api.get("/api/v1/auth/session", headers=bearer)).status_code == 200
        # Bearer-authenticated mutations need no CSRF token.
        listed = (await api.get("/api/v1/auth/sessions", headers=bearer)).json()["sessions"]
        own = listed[0]["id"]
        assert (await api.delete(f"/api/v1/auth/sessions/{own}", headers=bearer)).status_code == 204
        await api.aclose()


async def test_dev_login_hidden_when_disabled(make_client: Any) -> None:
    async for client, _fake, _drive in make_client(dev_login_enabled=False):
        response = await client.post("/api/v1/auth/dev-login", json={"email": "x@example.com"})
        assert response.status_code == 404


async def test_auth_endpoints_are_rate_limited(make_client: Any) -> None:
    async for client, _fake, _drive in make_client(auth_rate_limit_per_minute=3):
        codes = [
            (
                await client.post("/api/v1/auth/dev-login", json={"email": "r@example.com"})
            ).status_code
            for _ in range(4)
        ]
        assert codes[:3] == [200, 200, 200]
        assert codes[3] == 429


async def test_unauthenticated_requests_rejected(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        for path in ("/api/v1/auth/session", "/api/v1/auth/sessions"):
            response = await client.get(path)
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "unauthorized"
        garbage = {"Authorization": "Bearer not.a.jwt"}
        assert (await client.get("/api/v1/auth/session", headers=garbage)).status_code == 401


async def test_works_without_redis(make_client: Any) -> None:
    """A single free-tier instance can run with no Redis: state is in-process."""
    async for client, fake, _drive in make_client(redis_url=None, auth_rate_limit_per_minute=3):
        info = (await client.get("/ready")).json()
        assert "redis" not in {c["name"] for c in info["checks"]}
        assert info["status"] != "not_ready"

        fake.identity["sub"] = f"sub-{uuid.uuid4().hex}"
        response = await google_sign_in(client, fake)  # OAuth state round-trips in memory
        assert response.headers["location"] == f"{WEB}/files"
        assert (await client.get("/api/v1/auth/session")).status_code == 200

        codes = [
            (
                await client.post("/api/v1/auth/dev-login", json={"email": "m@example.com"})
            ).status_code
            for _ in range(4)
        ]
        assert codes[-1] == 429  # rate limiting still enforced
