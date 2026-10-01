"""/api/v1/storage — connect, inspect and disconnect storage providers."""

from __future__ import annotations

import secrets
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saige_api.api.deps import ResourcesDep, SessionDep
from saige_api.audit import record_audit
from saige_api.auth.deps import CurrentUserDep, get_current_user
from saige_api.auth.google import GoogleAuthError, PKCEPair
from saige_api.auth.state import DRIVE_CONNECT, PendingLogin, safe_next_path
from saige_api.core.errors import NotFoundError, ServiceUnavailableError, UnauthorizedError
from saige_api.core.logging import get_logger
from saige_api.models import StorageConnection
from saige_api.models.enums import AuditAction, StorageConnectionStatus
from saige_api.resources import Resources
from saige_api.schemas.storage import (
    DisconnectResponse,
    StorageConnectionListResponse,
    StorageConnectionSummary,
    StorageQuotaResponse,
)
from saige_api.schemas.system import ErrorResponse
from saige_api.storage.base import StorageError
from saige_api.storage.connections import StorageConnectionService

router = APIRouter(prefix="/storage", tags=["storage"])
logger = get_logger("saige_api.storage")

ERRORS: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}
DEFAULT_RETURN = "/settings#storage"


def connection_service(resources: Resources, db: AsyncSession) -> StorageConnectionService:
    if resources.google is None or resources.cipher is None:
        raise ServiceUnavailableError(
            "Google Drive isn't configured on this server "
            "(Google OAuth credentials and TOKEN_ENCRYPTION_KEY are required)."
        )
    return StorageConnectionService(
        db,
        session_factory=resources.session_factory,
        cipher=resources.cipher,
        google=resources.google,
        http=resources.external_http,
    )


def _summary(row: StorageConnection) -> StorageConnectionSummary:
    return StorageConnectionSummary(
        id=row.id,
        provider=row.provider,
        account_email=row.account_email,
        status=row.status,
        scopes=list(row.scopes or []),
        connected_at=row.connected_at,
        disconnected_at=row.disconnected_at,
        last_synced_at=row.last_synced_at,
    )


@router.get(
    "/connections",
    response_model=StorageConnectionListResponse,
    summary="List your storage connections",
    responses=ERRORS,
)
async def list_connections(auth: CurrentUserDep, db: SessionDep) -> StorageConnectionListResponse:
    rows = await db.scalars(
        select(StorageConnection)
        .where(StorageConnection.user_id == auth.user_id)
        .order_by(StorageConnection.connected_at.desc())
    )
    return StorageConnectionListResponse(connections=[_summary(r) for r in rows.all()])


@router.get(
    "/google-drive/connect",
    summary="Start connecting Google Drive (302 to Google consent)",
    status_code=302,
    responses=ERRORS,
)
async def connect_google_drive(
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: SessionDep,
    next_path: str | None = Query(default=None, alias="next", max_length=512),
) -> RedirectResponse:
    connection_service(resources, db)  # fail fast if not configured
    await resources.rate_limiter.hit(
        "drive_connect", str(auth.user_id), limit=resources.settings.auth_rate_limit_per_minute
    )
    assert resources.google is not None  # noqa: S101 - checked by connection_service
    pkce = PKCEPair.generate()
    nonce = secrets.token_urlsafe(24)
    state = await resources.oauth_state.create(
        PendingLogin(
            code_verifier=pkce.verifier,
            nonce=nonce,
            next_path=safe_next_path(next_path or DEFAULT_RETURN),
            purpose=DRIVE_CONNECT,
            user_id=str(auth.user_id),
        )
    )
    url = resources.google.authorization_url(
        state=state,
        nonce=nonce,
        code_challenge=pkce.challenge,
        scopes=("openid", "email", resources.settings.google_drive_scope),
        offline=True,
        login_hint=auth.user.email,
    )
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


def drive_redirect(
    resources: Resources, path: str, *, error: str | None = None
) -> RedirectResponse:
    base = resources.settings.web_public_url.rstrip("/")
    target, _, fragment = path.partition("#")
    sep = "&" if "?" in target else "?"
    query = f"{sep}drive_error={quote(error)}" if error else f"{sep}drive=connected"
    suffix = f"#{fragment}" if fragment else ""
    return RedirectResponse(f"{base}{target}{query}{suffix}", status_code=status.HTTP_302_FOUND)


async def complete_drive_connect(
    request: Request,
    resources: Resources,
    db: AsyncSession,
    pending: PendingLogin,
    code: str,
) -> RedirectResponse:
    """Second half of the Drive consent flow, called from the shared OAuth callback."""
    try:
        auth = await get_current_user(request, resources, db)
    except UnauthorizedError:
        return drive_redirect(resources, pending.next_path, error="signed_out")
    # Captured now: a rollback below expires ORM objects such as auth.user.
    user_id = auth.user_id
    # The consent must complete in the same account that started it.
    if pending.user_id != str(user_id):
        return drive_redirect(resources, pending.next_path, error="account_mismatch")
    try:
        service = connection_service(resources, db)
    except ServiceUnavailableError:
        return drive_redirect(resources, pending.next_path, error="drive_not_configured")
    assert resources.google is not None  # noqa: S101

    try:
        tokens = await resources.google.exchange_code_for_tokens(code, pending.code_verifier)
        if tokens.id_token is None:
            raise GoogleAuthError("missing_id_token")
        identity = await resources.google.verify_id_token(tokens.id_token, nonce=pending.nonce)
        if resources.settings.google_drive_scope not in tokens.scopes:
            # The user unticked the Drive permission on Google's consent screen.
            raise GoogleAuthError("drive_scope_not_granted")
        row = await service.connect_google_drive(
            user_id,
            identity,
            tokens,
            root_folder_name=resources.settings.google_drive_root_folder_name,
        )
    except (GoogleAuthError, StorageError) as exc:
        await db.rollback()
        logger.warning("drive_connect_failed", reason=exc.code)
        record_audit(
            db, request, AuditAction.OAUTH_CONNECT, user_id=user_id, outcome="failure",
            details={"provider": "google_drive", "reason": exc.code},
        )  # fmt: skip
        await db.commit()
        return drive_redirect(resources, pending.next_path, error=exc.code)

    record_audit(
        db, request, AuditAction.OAUTH_CONNECT, user_id=user_id,
        resource_type="storage_connection", resource_id=row.id,
        details={"provider": "google_drive", "scopes": list(row.scopes or [])},
    )  # fmt: skip
    await db.commit()
    return drive_redirect(resources, pending.next_path)


@router.post(
    "/connections/{connection_id}/disconnect",
    response_model=DisconnectResponse,
    summary="Disconnect a storage provider (revokes access; files stay in your storage)",
    responses=ERRORS,
)
async def disconnect(
    connection_id: uuid.UUID,
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: SessionDep,
) -> DisconnectResponse:
    service = connection_service(resources, db)
    row = await service.get_for_user(auth.user_id, connection_id)
    if row is None or row.status is StorageConnectionStatus.DISCONNECTED:
        raise NotFoundError("Storage connection not found")
    revoked = await service.disconnect(row)
    record_audit(
        db, request, AuditAction.OAUTH_DISCONNECT, user_id=auth.user_id,
        resource_type="storage_connection", resource_id=row.id,
        details={"provider": row.provider.value, "revoked_at_provider": revoked},
    )  # fmt: skip
    await db.commit()
    return DisconnectResponse(revoked_at_provider=revoked)


@router.get(
    "/connections/{connection_id}/quota",
    response_model=StorageQuotaResponse,
    summary="Storage usage reported by the provider",
    responses=ERRORS,
)
async def quota(
    connection_id: uuid.UUID, auth: CurrentUserDep, resources: ResourcesDep, db: SessionDep
) -> StorageQuotaResponse:
    service = connection_service(resources, db)
    row = await service.get_for_user(auth.user_id, connection_id)
    if row is None or row.status is StorageConnectionStatus.DISCONNECTED:
        raise NotFoundError("Storage connection not found")
    result = await service.provider(row).quota()
    return StorageQuotaResponse(
        limit_bytes=result.limit_bytes,
        usage_bytes=result.usage_bytes,
        usage_in_drive_bytes=result.usage_in_drive_bytes,
        usage_in_trash_bytes=result.usage_in_trash_bytes,
    )
