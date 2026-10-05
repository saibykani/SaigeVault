"""Email + password sign-in, lockout, two-step verification and takeover defences."""

from __future__ import annotations

import time
import uuid
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from pymongo.asynchronous.database import AsyncDatabase

from saige_api.auth import totp

pytestmark = pytest.mark.integration

WEB = "http://web.test"
PASSWORD = "plum orbit kettle 47"


def csrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("saige_csrf", "")}


def new_email() -> str:
    return f"pw-{uuid.uuid4().hex[:10]}@example.com"


async def register(
    client: httpx.AsyncClient, email: str, password: str = PASSWORD
) -> httpx.Response:
    return await client.post("/api/v1/auth/register", json={"email": email, "password": password})


def fresh(client: httpx.AsyncClient) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=client._transport, base_url=WEB)


async def test_register_then_sign_in(make_client: Any, db: AsyncDatabase[dict[str, Any]]) -> None:
    async for client, _fake, _drive in make_client():
        email = new_email()
        created = await register(client, email)
        assert created.status_code == 201, created.text
        assert created.json()["user"]["email"] == email
        assert "HttpOnly" in next(
            c for c in created.headers.get_list("set-cookie") if c.startswith("saige_access=")
        )

        other = fresh(client)
        login = await other.post(
            "/api/v1/auth/login", json={"email": email.upper(), "password": PASSWORD}
        )
        assert login.status_code == 200
        assert login.json()["mfa_required"] is False
        assert (await other.get("/api/v1/auth/session")).status_code == 200
        await other.aclose()

        user = await db.users.find_one({"email_lower": email.lower()})
        assert user is not None
        stored = user["password"]["hash"]
        assert stored.startswith("$argon2id$") and PASSWORD not in stored


async def test_wrong_password_and_unknown_email_look_identical(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        email = new_email()
        await register(fresh(client), email)
        wrong = await client.post("/api/v1/auth/login", json={"email": email, "password": "nope"})
        missing = await client.post(
            "/api/v1/auth/login", json={"email": new_email(), "password": "nope"}
        )
        assert wrong.status_code == missing.status_code == 401
        assert wrong.json()["error"]["code"] == missing.json()["error"]["code"]
        assert wrong.json()["error"]["message"] == missing.json()["error"]["message"]


async def test_account_locks_after_repeated_failures(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        email = new_email()
        await register(fresh(client), email)
        for _ in range(5):
            bad = await client.post("/api/v1/auth/login", json={"email": email, "password": "x"})
            assert bad.status_code == 401
        # Even the right password is refused while locked.
        locked = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        assert locked.status_code == 429


async def test_weak_and_duplicate_registrations_refused(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        weak = await register(client, new_email(), "password1234")
        assert weak.status_code == 400 and weak.json()["error"]["code"] == "weak_password"
        email = new_email()
        assert (await register(fresh(client), email)).status_code == 201
        assert (await register(fresh(client), email.upper())).status_code == 409


async def test_cross_site_login_refused(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": new_email(), "password": PASSWORD},
            headers={"Origin": "https://evil.example"},
        )
        assert response.status_code == 403


async def test_registration_rate_limited_per_ip(make_client: Any) -> None:
    async for client, _fake, _drive in make_client(registrations_per_hour_per_ip=2):
        codes = [(await register(fresh(client), new_email())).status_code for _ in range(3)]
        assert codes == [201, 201, 429]


async def _enable_totp(client: httpx.AsyncClient) -> tuple[str, list[str]]:
    setup = await client.post(
        "/api/v1/auth/mfa/totp/setup", json={"password": PASSWORD}, headers=csrf(client)
    )
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    assert setup.json()["otpauth_uri"].startswith("otpauth://totp/")
    # Use the previous step's code so the next sign-in can use the current one.
    code = totp.code_at(secret, time.time() - 30)
    enabled = await client.post(
        "/api/v1/auth/mfa/totp/enable", json={"code": code}, headers=csrf(client)
    )
    assert enabled.status_code == 200, enabled.text
    return secret, enabled.json()["recovery_codes"]


async def test_two_step_sign_in(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        email = new_email()
        await register(client, email)
        secret, recovery = await _enable_totp(client)
        assert len(recovery) == 10
        security = (await client.get("/api/v1/auth/security")).json()
        assert security["totp_enabled"] and security["recovery_codes_remaining"] == 10

        device = fresh(client)
        first = await device.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        body = first.json()
        assert body["mfa_required"] is True and body["session"] is None
        assert "saige_access" not in device.cookies  # no session until the second factor

        bad = await device.post(
            "/api/v1/auth/login/mfa", json={"mfa_token": body["mfa_token"], "code": "000000"}
        )
        assert bad.status_code == 400
        good = await device.post(
            "/api/v1/auth/login/mfa",
            json={"mfa_token": body["mfa_token"], "code": totp.code_at(secret)},
        )
        assert good.status_code == 200 and good.json()["session"]["user"]["email"] == email
        # The ticket is single-use.
        replay = await device.post(
            "/api/v1/auth/login/mfa",
            json={"mfa_token": body["mfa_token"], "code": totp.code_at(secret)},
        )
        assert replay.status_code == 401
        await device.aclose()

        # A recovery code works exactly once.
        for expected in (200, 400):
            other = fresh(client)
            ticket = (
                await other.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
            ).json()["mfa_token"]
            result = await other.post(
                "/api/v1/auth/login/mfa", json={"mfa_token": ticket, "code": recovery[0]}
            )
            assert result.status_code == expected
            await other.aclose()


async def test_mfa_ticket_attempts_are_limited(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        email = new_email()
        await register(client, email)
        await _enable_totp(client)
        device = fresh(client)
        ticket = (
            await device.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        ).json()["mfa_token"]
        codes = [
            (
                await device.post(
                    "/api/v1/auth/login/mfa", json={"mfa_token": ticket, "code": "123456"}
                )
            ).status_code
            for _ in range(6)
        ]
        assert codes[:5] == [400] * 5 and codes[5] == 429
        await device.aclose()


async def test_password_change_ends_other_sessions(make_client: Any) -> None:
    async for client, _fake, _drive in make_client():
        email = new_email()
        await register(client, email)
        other = fresh(client)
        await other.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})

        wrong = await client.put(
            "/api/v1/auth/password",
            json={"current_password": "wrong", "new_password": "violet canyon drum 93"},
            headers=csrf(client),
        )
        assert wrong.status_code == 400
        changed = await client.put(
            "/api/v1/auth/password",
            json={"current_password": PASSWORD, "new_password": "violet canyon drum 93"},
            headers=csrf(client),
        )
        assert changed.status_code == 204
        assert (await client.get("/api/v1/auth/session")).status_code == 200
        assert (await other.get("/api/v1/auth/session")).status_code == 401
        await other.aclose()


async def test_google_sign_in_evicts_squatted_password(make_client: Any) -> None:
    """Pre-hijacking: an attacker registers the victim's address first."""
    async for client, fake, _drive in make_client():
        victim_email = new_email()
        attacker = fresh(client)
        assert (await register(attacker, victim_email)).status_code == 201

        fake.identity["sub"] = f"sub-{uuid.uuid4().hex}"
        fake.identity["email"] = victim_email
        start = await client.get("/api/v1/auth/google/login")
        query = parse_qs(urlparse(start.headers["location"]).query)
        fake.codes["c"] = query["nonce"][0]
        await client.get(
            "/api/v1/auth/google/callback", params={"code": "c", "state": query["state"][0]}
        )
        assert (await client.get("/api/v1/auth/security")).json()["has_password"] is False

        assert (await attacker.get("/api/v1/auth/session")).status_code == 401
        retry = await attacker.post(
            "/api/v1/auth/login", json={"email": victim_email, "password": PASSWORD}
        )
        assert retry.status_code == 401
        await attacker.aclose()


async def test_google_user_can_add_password(make_client: Any) -> None:
    async for client, fake, _drive in make_client():
        email = new_email()
        fake.identity.update(sub=f"sub-{uuid.uuid4().hex}", email=email)
        start = await client.get("/api/v1/auth/google/login")
        query = parse_qs(urlparse(start.headers["location"]).query)
        fake.codes["c2"] = query["nonce"][0]
        await client.get(
            "/api/v1/auth/google/callback", params={"code": "c2", "state": query["state"][0]}
        )
        added = await client.put(
            "/api/v1/auth/password", json={"new_password": PASSWORD}, headers=csrf(client)
        )
        assert added.status_code == 204
        other = fresh(client)
        login = await other.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert login.status_code == 200
        await other.aclose()
