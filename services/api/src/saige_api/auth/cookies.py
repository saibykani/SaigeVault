"""Session cookies for the web client.

- saige_access   HttpOnly, path /api            short-lived access JWT
- saige_refresh  HttpOnly, path /api/v1/auth    refresh token (sent only to auth routes)
- saige_csrf     readable by JS, path /         double-submit CSRF token; also a
                                                "signed in" hint for the web UI

All SameSite=Lax and Secure outside local development. Tokens are never
exposed to JavaScript.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import Response

from saige_api.core.config import Settings

ACCESS_COOKIE = "saige_access"
REFRESH_COOKIE = "saige_refresh"
CSRF_COOKIE = "saige_csrf"
CSRF_HEADER = "x-csrf-token"

ACCESS_PATH = "/api"
REFRESH_PATH = "/api/v1/auth"


def set_session_cookies(
    response: Response,
    settings: Settings,
    *,
    access_token: str,
    access_ttl: timedelta,
    refresh_token: str,
    refresh_ttl: timedelta,
    csrf_token: str,
) -> None:
    secure = settings.secure_cookies
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=int(access_ttl.total_seconds()),
        path=ACCESS_PATH,
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=int(refresh_ttl.total_seconds()),
        path=REFRESH_PATH,
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=int(refresh_ttl.total_seconds()),
        path="/",
        httponly=False,
        secure=secure,
        samesite="lax",
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    for name, path in (
        (ACCESS_COOKIE, ACCESS_PATH),
        (REFRESH_COOKIE, REFRESH_PATH),
        (CSRF_COOKIE, "/"),
    ):
        response.delete_cookie(
            name,
            path=path,
            secure=settings.secure_cookies,
            httponly=name != CSRF_COOKIE,
            samesite="lax",
        )
