"""Storage connections: encrypted token custody, refresh, connect and disconnect.

Tokens are decrypted only in memory, only on the server, and only for the
duration of a provider call. They are never returned by any API.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from saige_api.auth.google import GoogleAuthError, GoogleIdentity, GoogleOAuthClient, GoogleTokens
from saige_api.core.logging import get_logger
from saige_api.crypto import DecryptionError, TokenCipher
from saige_api.models import StorageConnection
from saige_api.models.enums import StorageConnectionStatus, StorageProviderKind
from saige_api.storage.base import StorageAuthError, StorageError, StorageUnavailableError
from saige_api.storage.google_drive import GoogleDriveStorageProvider

logger = get_logger("saige_api.storage")

REFRESH_MARGIN = timedelta(seconds=90)


def _aad(connection_id: uuid.UUID, field: str) -> str:
    return f"storage_connection:{connection_id}:{field}"


class MissingRefreshTokenError(StorageError):
    code = "drive_offline_access_missing"


class ConnectionTokenSource:
    """AccessTokenSource backed by one storage connection row.

    Uses its own short transaction (row lock) so concurrent requests never
    refresh the same token twice and refreshed tokens are committed even if
    the caller's transaction later rolls back.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        cipher: TokenCipher,
        google: GoogleOAuthClient,
        connection_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        self._sessions = session_factory
        self._cipher = cipher
        self._google = google
        self._connection_id = connection_id
        self._user_id = user_id
        self._cached: tuple[str, datetime] | None = None

    async def get_token(self, *, force_refresh: bool = False) -> str:
        now = datetime.now(UTC)
        if self._cached and not force_refresh and self._cached[1] - REFRESH_MARGIN > now:
            return self._cached[0]
        failure: StorageError | None = None
        token: str | None = None
        # The transaction always commits, so a NEEDS_REAUTH status change is
        # persisted before the error is raised to the caller.
        async with self._sessions() as db, db.begin():
            row = await db.scalar(
                select(StorageConnection)
                .where(
                    StorageConnection.id == self._connection_id,
                    StorageConnection.user_id == self._user_id,
                )
                .with_for_update()
            )
            if row is None or row.status is not StorageConnectionStatus.ACTIVE:
                failure = StorageAuthError("storage connection is not active")
            else:
                token, failure = await self._token_for(row, now, force_refresh=force_refresh)
        if failure is not None:
            raise failure
        assert token is not None  # noqa: S101 - set whenever failure is None
        return token

    async def _token_for(
        self, row: StorageConnection, now: datetime, *, force_refresh: bool
    ) -> tuple[str | None, StorageError | None]:
        try:
            access = (
                self._cipher.decrypt(
                    row.encrypted_access_token, associated_data=_aad(row.id, "access")
                )
                if row.encrypted_access_token
                else None
            )
            refresh = (
                self._cipher.decrypt(
                    row.encrypted_refresh_token, associated_data=_aad(row.id, "refresh")
                )
                if row.encrypted_refresh_token
                else None
            )
        except DecryptionError:
            # Key changed or data tampered: the only safe recovery is reconnecting.
            row.status = StorageConnectionStatus.NEEDS_REAUTH
            logger.warning("storage_token_decrypt_failed", connection_id=str(row.id))
            return None, StorageAuthError("stored credentials unreadable")

        expires = row.access_token_expires_at
        if access and expires and not force_refresh and expires - REFRESH_MARGIN > now:
            self._cached = (access, expires)
            return access, None
        if not refresh:
            row.status = StorageConnectionStatus.NEEDS_REAUTH
            return None, StorageAuthError("no refresh token")
        try:
            tokens = await self._google.refresh_access_token(refresh)
        except GoogleAuthError as exc:
            if exc.code == "invalid_grant":
                row.status = StorageConnectionStatus.NEEDS_REAUTH
                logger.info("storage_reauth_required", connection_id=str(row.id))
                return None, StorageAuthError("access revoked")
            return None, StorageUnavailableError("token refresh failed")
        store_tokens(self._cipher, row, tokens)
        assert row.access_token_expires_at is not None  # noqa: S101 - set by store_tokens
        self._cached = (tokens.access_token, row.access_token_expires_at)
        return tokens.access_token, None


def store_tokens(cipher: TokenCipher, row: StorageConnection, tokens: GoogleTokens) -> None:
    row.encrypted_access_token = cipher.encrypt(
        tokens.access_token, associated_data=_aad(row.id, "access")
    )
    if tokens.refresh_token:
        row.encrypted_refresh_token = cipher.encrypt(
            tokens.refresh_token, associated_data=_aad(row.id, "refresh")
        )
    row.token_key_version = cipher.current_version
    row.access_token_expires_at = datetime.now(UTC) + timedelta(seconds=tokens.expires_in)
    if tokens.scopes:
        row.scopes = list(tokens.scopes)


class StorageConnectionService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        cipher: TokenCipher,
        google: GoogleOAuthClient,
        http: httpx.AsyncClient,
    ) -> None:
        self._db = db
        self._session_factory = session_factory
        self._cipher = cipher
        self._google = google
        self._http = http

    async def get_for_user(
        self, user_id: uuid.UUID, connection_id: uuid.UUID
    ) -> StorageConnection | None:
        return await self._db.scalar(
            select(StorageConnection).where(
                StorageConnection.id == connection_id, StorageConnection.user_id == user_id
            )
        )

    def provider(self, connection: StorageConnection) -> GoogleDriveStorageProvider:
        source = ConnectionTokenSource(
            session_factory=self._session_factory,
            cipher=self._cipher,
            google=self._google,
            connection_id=connection.id,
            user_id=connection.user_id,
        )
        return GoogleDriveStorageProvider(self._http, source)

    async def connect_google_drive(
        self,
        user_id: uuid.UUID,
        identity: GoogleIdentity,
        tokens: GoogleTokens,
        *,
        root_folder_name: str,
    ) -> StorageConnection:
        row = await self._db.scalar(
            select(StorageConnection).where(
                StorageConnection.user_id == user_id,
                StorageConnection.provider == StorageProviderKind.GOOGLE_DRIVE,
                StorageConnection.provider_account_id == identity.subject,
            )
        )
        if row is None:
            row = StorageConnection(
                id=uuid.uuid4(),
                user_id=user_id,
                provider=StorageProviderKind.GOOGLE_DRIVE,
                provider_account_id=identity.subject,
                scopes=[],
                token_key_version=self._cipher.current_version,
            )
            self._db.add(row)
        if not tokens.refresh_token and not row.encrypted_refresh_token:
            raise MissingRefreshTokenError("Google did not grant offline access")
        row.account_email = identity.email
        row.status = StorageConnectionStatus.ACTIVE
        row.connected_at = datetime.now(UTC)
        row.disconnected_at = None
        store_tokens(self._cipher, row, tokens)
        # Commit the credentials before calling Drive with them.
        await self._db.flush()
        await self._db.commit()

        provider = self.provider(row)
        root = await provider.ensure_root_folder(root_folder_name)
        row.root_folder_id = root.id
        if not row.changes_page_token:
            row.changes_page_token = await provider.get_start_page_token()
        await self._db.flush()
        return row

    async def disconnect(self, row: StorageConnection) -> bool:
        """Revoke at Google (best effort) and wipe credentials. Files stay in Drive."""
        revoked = False
        if row.encrypted_refresh_token:
            try:
                token = self._cipher.decrypt(
                    row.encrypted_refresh_token, associated_data=_aad(row.id, "refresh")
                )
                revoked = await self._google.revoke(token)
            except DecryptionError:
                revoked = False
        row.encrypted_access_token = None
        row.encrypted_refresh_token = None
        row.access_token_expires_at = None
        row.status = StorageConnectionStatus.DISCONNECTED
        row.disconnected_at = datetime.now(UTC)
        await self._db.flush()
        return revoked
