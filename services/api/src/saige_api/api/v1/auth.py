"""/api/v1/auth — sign-in, refresh, sign-out and session management."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from saige_api.api.deps import DbDep, ResourcesDep
from saige_api.audit import client_ip, record_audit, record_security_event, user_agent
from saige_api.auth.cookies import REFRESH_COOKIE, clear_session_cookies, set_session_cookies
from saige_api.auth.deps import CurrentUserDep, verify_csrf
from saige_api.auth.google import GoogleAuthError, PKCEPair
from saige_api.auth.sessions import (
    ClientInfo,
    IssuedSession,
    RefreshOutcome,
    RevokeReason,
    SessionService,
)
from saige_api.auth.state import PendingLogin, safe_next_path
from saige_api.auth.tokens import new_csrf_token
from saige_api.auth.users import user_for_dev_login, user_for_google_identity
from saige_api.core.errors import AppError, NotFoundError, UnauthorizedError, error_response
from saige_api.core.logging import get_logger
from saige_api.enums import AuditAction, ClientPlatform, SecuritySeverity
from saige_api.resources import Resources
from saige_api.schemas.auth import (
    DevLoginRequest,
    RefreshRequest,
    RefreshResponse,
    SessionListResponse,
    SessionResponse,
    SessionSummary,
    TokenPair,
    user_profile,
)
from saige_api.schemas.system import ErrorResponse

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("saige_api.auth")

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


def _client(request: Request, platform: ClientPlatform = ClientPlatform.WEB) -> ClientInfo:
    return ClientInfo(
        platform=platform, user_agent=user_agent(request), ip_address=client_ip(request)
    )


async def _rate_limit(resources: Resources, request: Request, bucket: str) -> None:
    await resources.rate_limiter.hit(
        bucket,
        client_ip(request) or "unknown",
        limit=resources.settings.auth_rate_limit_per_minute,
    )


def _web_redirect(resources: Resources, path: str) -> RedirectResponse:
    base = resources.settings.web_public_url.rstrip("/")
    return RedirectResponse(f"{base}{path}", status_code=status.HTTP_302_FOUND)


def _login_error(resources: Resources, code: str) -> RedirectResponse:
    return _web_redirect(resources, f"/login?error={quote(code)}")


def _start_session_response(
    response: Response, resources: Resources, issued: IssuedSession
) -> datetime:
    access = resources.tokens.issue_access_token(issued.user_id, issued.session_id)
    set_session_cookies(
        response,
        resources.settings,
        access_token=access,
        access_ttl=resources.tokens.access_ttl,
        refresh_token=issued.refresh_token,
        refresh_ttl=resources.refresh_ttl,
        csrf_token=new_csrf_token(),
    )
    return datetime.now(UTC) + resources.tokens.access_ttl


def _unauthorized_and_clear(request: Request, resources: Resources, message: str) -> JSONResponse:
    """401 that also clears session cookies (raising would discard them)."""
    response = error_response(request, status.HTTP_401_UNAUTHORIZED, "unauthorized", message)
    clear_session_cookies(response, resources.settings)
    return response


@router.get("/google/login", summary="Start Google sign-in", status_code=302)
async def google_login(
    request: Request,
    resources: ResourcesDep,
    next_path: str | None = Query(default=None, alias="next", max_length=512),
) -> RedirectResponse:
    await _rate_limit(resources, request, "google_login")
    if resources.google is None:
        return _login_error(resources, "google_not_configured")
    pkce = PKCEPair.generate()
    nonce = secrets.token_urlsafe(24)
    state = await resources.oauth_state.create(
        PendingLogin(code_verifier=pkce.verifier, nonce=nonce, next_path=safe_next_path(next_path))
    )
    url = resources.google.authorization_url(
        state=state, nonce=nonce, code_challenge=pkce.challenge
    )
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get("/google/callback", summary="Google OAuth callback", status_code=302)
async def google_callback(  # noqa: PLR0911 - one early return per failure mode
    request: Request,
    *,
    resources: ResourcesDep,
    db: DbDep,
    code: str | None = Query(default=None, max_length=2048),
    state: str | None = Query(default=None, max_length=128),
    error: str | None = Query(default=None, max_length=128),
) -> RedirectResponse:
    await _rate_limit(resources, request, "google_callback")
    if resources.google is None:
        return _login_error(resources, "google_not_configured")
    # Consume state first so it is single-use even when Google reports an error.
    pending = await resources.oauth_state.consume(state or "")
    if error:
        return _login_error(
            resources, "access_denied" if error == "access_denied" else "google_error"
        )
    if pending is None:
        return _login_error(resources, "invalid_state")
    if not code:
        return _login_error(resources, "missing_code")
    try:
        id_token = await resources.google.exchange_code(code, pending.code_verifier)
        identity = await resources.google.verify_id_token(id_token, nonce=pending.nonce)
        user = await user_for_google_identity(db, identity)
    except GoogleAuthError as exc:
        logger.warning("google_login_failed", reason=exc.code)
        await record_audit(
            db,
            request,
            AuditAction.LOGIN,
            user_id=None,
            outcome="failure",
            details={"method": "google", "reason": exc.code},
        )
        return _login_error(resources, exc.code)
    except AppError as exc:
        return _login_error(resources, exc.code)

    issued = await SessionService(db, resources.refresh_ttl).create(user.id, _client(request))
    await record_audit(
        db,
        request,
        AuditAction.LOGIN,
        user_id=user.id,
        details={"method": "google", "session_id": str(issued.session_id)},
    )
    response = _web_redirect(resources, pending.next_path)
    _start_session_response(response, resources, issued)
    return response


@router.post(
    "/dev-login",
    summary="Development-only sign-in by email",
    response_model=SessionResponse,
    responses={404: {"model": ErrorResponse}, **ERROR_RESPONSES},
)
async def dev_login(
    body: DevLoginRequest,
    request: Request,
    response: Response,
    resources: ResourcesDep,
    db: DbDep,
) -> SessionResponse:
    settings = resources.settings
    if not settings.dev_login_enabled or settings.is_production:
        # Indistinguishable from a route that does not exist.
        raise NotFoundError("Not Found")
    await _rate_limit(resources, request, "dev_login")
    user = await user_for_dev_login(db, str(body.email), body.display_name)
    issued = await SessionService(db, resources.refresh_ttl).create(user.id, _client(request))
    await record_audit(
        db,
        request,
        AuditAction.LOGIN,
        user_id=user.id,
        details={"method": "dev", "session_id": str(issued.session_id)},
    )
    access_expires_at = _start_session_response(response, resources, issued)
    return SessionResponse(
        user=user_profile(user),
        session_id=issued.session_id,
        access_expires_at=access_expires_at,
    )


@router.post(
    "/refresh",
    summary="Rotate the refresh token and issue a new access token",
    response_model=RefreshResponse,
    responses=ERROR_RESPONSES,
)
async def refresh(
    request: Request,
    response: Response,
    resources: ResourcesDep,
    db: DbDep,
    body: RefreshRequest | None = None,
) -> RefreshResponse | JSONResponse:
    await _rate_limit(resources, request, "refresh")
    body_token = body.refresh_token if body else None
    token = body_token or request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise UnauthorizedError("Not signed in")
    via_cookie = body_token is None
    if via_cookie:
        verify_csrf(request)

    platform = ClientPlatform.WEB if via_cookie else ClientPlatform.API
    result = await SessionService(db, resources.refresh_ttl).rotate(
        token, _client(request, platform)
    )

    if result.outcome is RefreshOutcome.REUSE_DETECTED:
        await record_security_event(
            db,
            request,
            "refresh_token_reuse",
            SecuritySeverity.HIGH,
            "A previously rotated refresh token was presented; the session was revoked.",
            user_id=result.user_id,
            details={"session_id": str(result.session_id)},
        )
        return _unauthorized_and_clear(
            request, resources, "Session revoked for your protection. Please sign in again."
        )
    if result.outcome is RefreshOutcome.RACE:
        # Another tab refreshed a moment ago; its cookies are already in the jar.
        raise UnauthorizedError("Session was just refreshed; retry the request")
    if result.outcome is RefreshOutcome.INVALID or result.issued is None:
        return _unauthorized_and_clear(request, resources, "Session expired. Please sign in again.")
    issued = result.issued
    if via_cookie:
        expires = _start_session_response(response, resources, issued)
        return RefreshResponse(session_id=issued.session_id, access_expires_at=expires)
    access = resources.tokens.issue_access_token(issued.user_id, issued.session_id)
    ttl = resources.tokens.access_ttl
    return RefreshResponse(
        session_id=issued.session_id,
        access_expires_at=datetime.now(UTC) + ttl,
        tokens=TokenPair(
            access_token=access,
            refresh_token=issued.refresh_token,
            expires_in=int(ttl.total_seconds()),
        ),
    )


@router.post("/logout", summary="Sign out of this session", status_code=204)
async def logout(request: Request, resources: ResourcesDep, db: DbDep) -> Response:
    sessions = SessionService(db, resources.refresh_ttl)
    token = request.cookies.get(REFRESH_COOKIE)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    if token:
        verify_csrf(request)
        found = await sessions.find_family_by_refresh_token(token)
        if found:
            user_id, family_id = found
            await sessions.revoke_family(user_id, family_id, RevokeReason.LOGOUT)
            await record_audit(
                db,
                request,
                AuditAction.LOGOUT,
                user_id=user_id,
                details={"session_id": str(family_id)},
            )
    clear_session_cookies(response, resources.settings)
    return response


@router.get(
    "/session",
    summary="Current user and session",
    response_model=SessionResponse,
    responses=ERROR_RESPONSES,
)
async def current_session(auth: CurrentUserDep) -> SessionResponse:
    return SessionResponse(
        user=user_profile(auth.user),
        session_id=auth.session_id,
        access_expires_at=auth.access_expires_at,
    )


@router.get(
    "/sessions",
    summary="List active sessions",
    response_model=SessionListResponse,
    responses=ERROR_RESPONSES,
)
async def list_sessions(
    auth: CurrentUserDep, resources: ResourcesDep, db: DbDep
) -> SessionListResponse:
    rows = await SessionService(db, resources.refresh_ttl).list_active(auth.user_id)
    return SessionListResponse(
        sessions=[
            SessionSummary(
                id=row.family_id,
                platform=row.platform,
                user_agent=row.user_agent,
                ip_address=str(row.ip_address) if row.ip_address else None,
                started_at=started_at,
                last_seen_at=row.last_seen_at,
                expires_at=row.expires_at,
                current=row.family_id == auth.session_id,
            )
            for row, started_at in rows
        ]
    )


@router.delete(
    "/sessions/{session_id}",
    summary="Revoke a session",
    status_code=204,
    responses={404: {"model": ErrorResponse}, **ERROR_RESPONSES},
)
async def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: DbDep,
) -> Response:
    revoked = await SessionService(db, resources.refresh_ttl).revoke_family(
        auth.user_id, session_id, RevokeReason.USER_REVOKED
    )
    if revoked == 0:
        raise NotFoundError("Session not found")
    await record_audit(
        db,
        request,
        AuditAction.LOGOUT,
        user_id=auth.user_id,
        details={"session_id": str(session_id), "reason": "user_revoked"},
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    if session_id == auth.session_id:
        clear_session_cookies(response, resources.settings)
    return response
