from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from saige_api.auth.state import safe_next_path
from saige_api.auth.tokens import (
    InvalidTokenError,
    TokenService,
    hash_token,
    new_refresh_token,
)

KEY = "k" * 48


def test_access_token_round_trip() -> None:
    service = TokenService(KEY, 900)
    user_id, session_id = uuid.uuid4(), uuid.uuid4()
    claims = service.verify_access_token(service.issue_access_token(user_id, session_id))
    assert claims.user_id == user_id
    assert claims.session_id == session_id


def test_expired_token_rejected() -> None:
    service = TokenService(KEY, 60)
    token = service.issue_access_token(
        uuid.uuid4(), uuid.uuid4(), now=datetime.now(UTC) - timedelta(minutes=5)
    )
    with pytest.raises(InvalidTokenError):
        service.verify_access_token(token)


def test_token_signed_with_other_key_rejected() -> None:
    token = TokenService("x" * 48, 900).issue_access_token(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(InvalidTokenError):
        TokenService(KEY, 900).verify_access_token(token)


def test_alg_none_and_wrong_type_rejected() -> None:
    service = TokenService(KEY, 900)
    now = int(datetime.now(UTC).timestamp())
    base = {
        "iss": "saige-api", "aud": "saige", "sub": str(uuid.uuid4()),
        "sid": str(uuid.uuid4()), "iat": now, "exp": now + 600,
    }  # fmt: skip
    unsigned = jwt.encode({**base, "typ": "access"}, key=None, algorithm="none")
    with pytest.raises(InvalidTokenError):
        service.verify_access_token(unsigned)
    refresh_typed = jwt.encode({**base, "typ": "refresh"}, KEY, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        service.verify_access_token(refresh_typed)


def test_short_signing_key_refused() -> None:
    with pytest.raises(ValueError, match="32"):
        TokenService("short", 900)


def test_refresh_tokens_are_random_and_hashed() -> None:
    a, b = new_refresh_token(), new_refresh_token()
    assert a != b
    assert len(a) >= 64
    assert hash_token(a) != a
    assert len(hash_token(a)) == 64


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (None, "/"),
        ("/files", "/files"),
        ("/files?view=grid", "/files?view=grid"),
        ("https://evil.example", "/"),
        ("//evil.example", "/"),
        ("/\\evil.example", "/"),
        ("javascript:alert(1)", "/"),
        ("/ok\r\nSet-Cookie: x", "/"),
    ],
)
def test_safe_next_path(candidate: str | None, expected: str) -> None:
    assert safe_next_path(candidate) == expected
