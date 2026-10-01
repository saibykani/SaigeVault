"""Access tokens (short-lived JWT) and refresh tokens (opaque, hashed at rest)."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

ISSUER = "saige-api"
AUDIENCE = "saige"
ALGORITHM = "HS256"
LEEWAY_SECONDS = 10


class InvalidTokenError(Exception):
    """Raised for any malformed, expired or tampered token."""


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID  # the session family, stable across refresh rotation
    expires_at: datetime


class TokenService:
    def __init__(self, signing_key: str, access_ttl_seconds: int) -> None:
        if len(signing_key) < 32:
            raise ValueError("signing key must be at least 32 characters")
        self._key = signing_key
        self._ttl = timedelta(seconds=access_ttl_seconds)

    @property
    def access_ttl(self) -> timedelta:
        return self._ttl

    def issue_access_token(
        self, user_id: uuid.UUID, session_id: uuid.UUID, *, now: datetime | None = None
    ) -> str:
        issued = now or datetime.now(UTC)
        payload = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": str(user_id),
            "sid": str(session_id),
            "typ": "access",
            "iat": int(issued.timestamp()),
            "exp": int((issued + self._ttl).timestamp()),
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(payload, self._key, algorithm=ALGORITHM)

    def verify_access_token(self, token: str) -> AccessClaims:
        try:
            payload = jwt.decode(
                token,
                self._key,
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                issuer=ISSUER,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "sub", "sid", "iss", "aud"]},
            )
            if payload.get("typ") != "access":
                raise InvalidTokenError("wrong token type")
            return AccessClaims(
                user_id=uuid.UUID(payload["sub"]),
                session_id=uuid.UUID(payload["sid"]),
                expires_at=datetime.fromtimestamp(payload["exp"], UTC),
            )
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise InvalidTokenError(type(exc).__name__) from exc


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """SHA-256 is appropriate here: refresh tokens are 384-bit random values,
    so a slow password hash adds nothing."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)
