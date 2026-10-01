from __future__ import annotations

import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from google_fake import CLIENT_ID, FakeGoogle

from saige_api.auth.google import GoogleAuthError, GoogleOAuthClient, PKCEPair


def make_client(fake: FakeGoogle) -> GoogleOAuthClient:
    return GoogleOAuthClient(
        client_id=CLIENT_ID,
        client_secret="test-secret",
        redirect_uri="http://localhost:3000/api/v1/auth/google/callback",
        http=httpx.AsyncClient(transport=fake.transport()),
    )


def test_authorization_url_uses_pkce_state_and_nonce() -> None:
    pkce = PKCEPair.generate()
    url = make_client(FakeGoogle()).authorization_url(
        state="s1", nonce="n1", code_challenge=pkce.challenge
    )
    query = parse_qs(urlparse(url).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [pkce.challenge]
    assert query["state"] == ["s1"]
    assert query["nonce"] == ["n1"]
    assert query["scope"] == ["openid email profile"]
    assert "client_secret" not in query


def test_pkce_challenge_is_s256_of_verifier() -> None:
    pkce = PKCEPair.generate()
    expected = base64.urlsafe_b64encode(hashlib.sha256(pkce.verifier.encode()).digest())
    assert pkce.challenge == expected.rstrip(b"=").decode()
    assert 43 <= len(pkce.verifier) <= 128


async def test_valid_id_token_is_accepted() -> None:
    fake = FakeGoogle()
    identity = await make_client(fake).verify_id_token(fake.id_token("n1"), nonce="n1")
    assert identity.email == "alice@example.com"
    assert identity.subject == "google-sub-1"


@pytest.mark.parametrize(
    ("overrides", "nonce", "code"),
    [
        ({}, "different", "nonce_mismatch"),
        ({"aud": "someone-else"}, "n1", "invalid_id_token"),
        ({"iss": "https://evil.example"}, "n1", "invalid_id_token"),
        ({"exp": 1}, "n1", "invalid_id_token"),
        ({"email_verified": False}, "n1", "email_not_verified"),
    ],
)
async def test_invalid_id_tokens_are_rejected(
    overrides: dict[str, object], nonce: str, code: str
) -> None:
    fake = FakeGoogle()
    with pytest.raises(GoogleAuthError) as excinfo:
        await make_client(fake).verify_id_token(fake.id_token("n1", **overrides), nonce=nonce)
    assert excinfo.value.code == code


async def test_token_signed_by_unknown_key_is_rejected() -> None:
    attacker = FakeGoogle()
    with pytest.raises(GoogleAuthError):
        await make_client(FakeGoogle()).verify_id_token(attacker.id_token("n1"), nonce="n1")


async def test_failed_code_exchange() -> None:
    with pytest.raises(GoogleAuthError) as excinfo:
        await make_client(FakeGoogle()).exchange_code("unknown-code", "verifier")
    assert excinfo.value.code == "code_exchange_failed"
