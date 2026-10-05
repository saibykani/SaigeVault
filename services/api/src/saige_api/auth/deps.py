"""Authentication and CSRF dependencies.

Every route that touches user data depends on `CurrentUserDep`. Credentials
are accepted from either:
- `Authorization: Bearer <access token>` (mobile / API clients), or
- the `saige_access` HttpOnly cookie (web), in which case unsafe methods
  also require a matching `X-CSRF-Token` header (double-submit).
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Request

from saige_api.api.deps import DbDep, ResourcesDep
from saige_api.auth.cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER
from saige_api.auth.sessions import SessionService
from saige_api.auth.tokens import InvalidTokenError
from saige_api.core.errors import ForbiddenError, UnauthorizedError
from saige_api.db import Doc
from saige_api.enums import UserStatus

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: Doc
    session_id: uuid.UUID
    via_cookie: bool
    access_expires_at: datetime

    @property
    def user_id(self) -> uuid.UUID:
        user_id: uuid.UUID = self.user.id
        return user_id


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def verify_csrf(request: Request) -> None:
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get(CSRF_HEADER, "")
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise ForbiddenError("Missing or invalid CSRF token")


async def get_current_user(request: Request, resources: ResourcesDep, db: DbDep) -> AuthContext:
    token = _bearer_token(request)
    via_cookie = token is None
    if token is None:
        token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise UnauthorizedError("Not signed in")
    try:
        claims = resources.tokens.verify_access_token(token)
    except InvalidTokenError as exc:
        raise UnauthorizedError("Session expired or invalid") from exc

    sessions = SessionService(db, refresh_ttl=resources.refresh_ttl)
    if not await sessions.is_active(claims.user_id, claims.session_id):
        raise UnauthorizedError("Session has ended")
    raw = await db.users.find_one(
        {"_id": claims.user_id, "deleted_at": None, "status": UserStatus.ACTIVE.value}
    )
    user = Doc(raw) if raw is not None else None
    if user is None:
        raise UnauthorizedError("Account unavailable")
    if via_cookie and request.method not in SAFE_METHODS:
        verify_csrf(request)
    return AuthContext(
        user=user,
        session_id=claims.session_id,
        via_cookie=via_cookie,
        access_expires_at=claims.expires_at,
    )


CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]
