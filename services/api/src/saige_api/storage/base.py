"""Provider-independent storage interface (ADR-0002).

Google Drive is the first implementation; OneDrive, Dropbox, S3 or Azure Blob
can be added by implementing `StorageProvider` without touching callers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from saige_api.models.enums import StorageProviderKind


class StorageError(Exception):
    """Base class. `code` is safe to show to users and to log."""

    code = "storage_error"


class StorageNotFoundError(StorageError):
    code = "storage_not_found"


class StorageAuthError(StorageError):
    """Credentials were revoked or expired: the user must reconnect."""

    code = "storage_reauth_required"


class StorageQuotaExceededError(StorageError):
    code = "storage_quota_exceeded"


class StorageUnavailableError(StorageError):
    code = "storage_unavailable"


class StoragePermissionError(StorageError):
    code = "storage_permission_denied"


@dataclass(frozen=True, slots=True)
class StorageItem:
    id: str
    name: str
    mime_type: str
    is_folder: bool
    size: int | None = None
    parent_ids: tuple[str, ...] = ()
    modified_at: datetime | None = None
    sha256: str | None = None
    md5: str | None = None
    trashed: bool = False
    revision_id: str | None = None


@dataclass(frozen=True, slots=True)
class ListPage:
    items: list[StorageItem]
    next_page_token: str | None = None


@dataclass(frozen=True, slots=True)
class StorageRevision:
    id: str
    modified_at: datetime | None
    size: int | None
    mime_type: str | None


@dataclass(frozen=True, slots=True)
class StorageChange:
    file_id: str
    removed: bool
    item: StorageItem | None


@dataclass(frozen=True, slots=True)
class ChangePage:
    changes: list[StorageChange] = field(default_factory=list)
    next_page_token: str | None = None
    new_start_page_token: str | None = None


@dataclass(frozen=True, slots=True)
class StorageQuota:
    limit_bytes: int | None  # None = unlimited
    usage_bytes: int
    usage_in_drive_bytes: int | None = None
    usage_in_trash_bytes: int | None = None


class StorageProvider(Protocol):
    kind: StorageProviderKind

    async def ensure_root_folder(self, name: str) -> StorageItem: ...
    async def create_folder(self, name: str, parent_id: str) -> StorageItem: ...
    async def list_folder(
        self, folder_id: str, *, page_token: str | None = None, page_size: int = 100
    ) -> ListPage: ...
    async def get_item(self, item_id: str) -> StorageItem: ...
    async def upload(
        self,
        *,
        name: str,
        parent_id: str,
        mime_type: str,
        size: int,
        content: AsyncIterator[bytes],
    ) -> StorageItem: ...
    def download(self, item_id: str) -> AsyncIterator[bytes]: ...
    async def rename(self, item_id: str, new_name: str) -> StorageItem: ...
    async def move(self, item_id: str, new_parent_id: str) -> StorageItem: ...
    async def trash(self, item_id: str) -> StorageItem: ...
    async def restore(self, item_id: str) -> StorageItem: ...
    async def delete_permanently(self, item_id: str) -> None: ...
    async def list_revisions(self, item_id: str) -> list[StorageRevision]: ...
    async def get_start_page_token(self) -> str: ...
    async def list_changes(self, page_token: str) -> ChangePage: ...
    async def quota(self) -> StorageQuota: ...
