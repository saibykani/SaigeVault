from __future__ import annotations

import hashlib

import httpx
import pytest

from saige_api.auth import passwords, totp


def test_hash_is_argon2id_and_verifies() -> None:
    stored = passwords.hash_password("correct horse battery staple")
    assert stored.startswith("$argon2id$")
    assert passwords.verify_password(stored, "correct horse battery staple")
    assert not passwords.verify_password(stored, "correct horse battery stapl")


def test_unknown_account_never_verifies() -> None:
    # The dummy hash's own password must not unlock a missing account.
    assert not passwords.verify_password(None, "saige-dummy-password-for-timing")
    assert not passwords.verify_password("not-a-hash", "anything")


def test_unicode_is_normalised() -> None:
    stored = passwords.hash_password("ｃａｆé-long-password")  # full-width + composed
    assert passwords.verify_password(stored, "café-long-password")


@pytest.mark.parametrize(
    ("candidate", "reason"),
    [
        ("short", "at least 12"),
        ("x" * 129, "at most 128"),
        ("password1234", "too easy"),
        ("aaaaaaaaaaaaaa", "too easy"),
        ("alice.smith-2026!", "email address"),
    ],
)
def test_policy_rejects_weak_passwords(candidate: str, reason: str) -> None:
    with pytest.raises(passwords.WeakPasswordError, match=reason):
        passwords.check_policy(candidate, email="alice.smith@example.com")


def test_policy_accepts_passphrase() -> None:
    passwords.check_policy("plum orbit kettle 47", email="alice@example.com")


async def test_breach_check_uses_k_anonymity() -> None:
    password = "plum orbit kettle 47"
    digest = hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, text=f"0000000000000000000000000000000000A:3\n{digest[5:]}:12")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert await passwords.is_breached(http, password)
    assert seen == [passwords.PWNED_RANGE_URL + digest[:5]]  # only the prefix leaves


async def test_breach_check_fails_open() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert not await passwords.is_breached(http, "plum orbit kettle 47")


# -- TOTP ---------------------------------------------------------------------

RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # RFC 6238 test key "12345678901234567890"


@pytest.mark.parametrize(
    ("now", "code"), [(59, "287082"), (1111111109, "081804"), (2000000000, "279037")]
)
def test_totp_matches_rfc_6238_vectors(now: int, code: str) -> None:
    assert totp.code_at(RFC_SECRET, now) == code


def test_totp_accepts_drift_and_rejects_replay() -> None:
    now = 1_700_000_000.0
    previous = totp.code_at(RFC_SECRET, now - 30)
    step = totp.verify(RFC_SECRET, previous, last_used_step=None, now=now)
    assert step == totp.current_step(now) - 1
    assert totp.verify(RFC_SECRET, previous, last_used_step=step, now=now) == -1
    assert (
        totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, now - 90), last_used_step=None, now=now)
        == -1
    )
    assert totp.verify(RFC_SECRET, "12345", last_used_step=None, now=now) == -1


def test_provisioning_uri_and_recovery_codes() -> None:
    secret = totp.new_secret()
    assert len(secret) == 32
    uri = totp.provisioning_uri(secret, account="a@example.com")
    assert uri.startswith("otpauth://totp/Saige%20Vault%3Aa%40example.com?secret=")
    codes = totp.new_recovery_codes()
    assert len(set(codes)) == 10
    assert totp.hash_recovery_code(codes[0].upper()) == totp.hash_recovery_code(codes[0])
