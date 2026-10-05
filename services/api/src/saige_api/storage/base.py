"""Object storage interface. Cloudflare R2 in production, in-memory for tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import BinaryIO, Protocol


class StorageError(Exception):
    """Base class. `code` is safe to show to users and to log."""

    code = "storage_error"


class StorageNotFoundError(StorageError):
    code = "storage_not_found"


class StorageUnavailableError(StorageError):
    code = "storage_unavailable"


class StorageNotConfiguredError(StorageError):
    code = "storage_not_configured"


class ObjectStore(Protocol):
    name: str

    async def put(self, key: str, stream: BinaryIO, *, size: int, content_type: str) -> None: ...

    def get(self, key: str) -> AsyncIterator[bytes]: ...

    async def delete(self, key: str) -> None: ...

    async def ping(self) -> None: ...
