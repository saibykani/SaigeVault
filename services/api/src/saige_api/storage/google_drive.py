"""Google Drive v3 implementation of StorageProvider (REST over httpx).

- Authorization: bearer access token from an AccessTokenSource; a 401 forces
  one token refresh and a retry.
- Resilience: 429, 5xx and Drive rate-limit 403s are retried with capped
  exponential backoff and jitter.
- Safety: IDs are validated before use, so they can never inject into Drive
  query strings; no caller-supplied text is ever placed in `q`.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from typing import Any, Protocol

import httpx

from saige_api.core.logging import get_logger
from saige_api.models.enums import StorageProviderKind
from saige_api.storage.base import (
    ChangePage,
    ListPage,
    StorageApiDisabledError,
    StorageAuthError,
    StorageChange,
    StorageError,
    StorageItem,
    StorageNotFoundError,
    StoragePermissionError,
    StorageQuota,
    StorageQuotaExceededError,
    StorageRevision,
    StorageUnavailableError,
)

API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"
FILE_FIELDS = (
    "id,name,mimeType,size,parents,modifiedTime,trashed,md5Checksum,sha256Checksum,headRevisionId"
)
ROOT_MARKER_KEY = "saigeVault"
ROOT_MARKER_VALUE = "root"
MULTIPART_LIMIT = 5 * 1024 * 1024
RESUMABLE_CHUNK = 8 * 1024 * 1024  # multiple of 256 KiB, as Drive requires
MAX_ATTEMPTS = 4
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,256}$")
_RATE_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "backendError"}
_API_DISABLED_REASONS = {"accessNotConfigured", "SERVICE_DISABLED"}
_SCOPE_REASONS = {"insufficientPermissions", "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}

logger = get_logger("saige_api.storage.google_drive")


class AccessTokenSource(Protocol):
    async def get_token(self, *, force_refresh: bool = False) -> str: ...


def check_id(item_id: str) -> str:
    if not _ID_PATTERN.match(item_id):
        raise StorageNotFoundError("invalid storage id")
    return item_id


def _parse_time(value: object) -> datetime | None:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None


def to_item(data: dict[str, Any]) -> StorageItem:
    size = data.get("size")
    return StorageItem(
        id=str(data["id"]),
        name=str(data.get("name", "")),
        mime_type=str(data.get("mimeType", "application/octet-stream")),
        is_folder=data.get("mimeType") == FOLDER_MIME,
        size=int(size) if size is not None else None,
        parent_ids=tuple(data.get("parents") or ()),
        modified_at=_parse_time(data.get("modifiedTime")),
        sha256=data.get("sha256Checksum"),
        md5=data.get("md5Checksum"),
        trashed=bool(data.get("trashed", False)),
        revision_id=data.get("headRevisionId"),
    )


def _error_reasons(response: httpx.Response) -> set[str]:
    """Reasons from both Drive's legacy `errors` list and the newer `details` list."""
    try:
        error = response.json().get("error", {})
        entries = [*error.get("errors", []), *error.get("details", [])]
        return {str(e["reason"]) for e in entries if isinstance(e, dict) and e.get("reason")}
    except (ValueError, AttributeError, TypeError):
        return set()


class GoogleDriveStorageProvider:
    kind = StorageProviderKind.GOOGLE_DRIVE

    def __init__(
        self,
        http: httpx.AsyncClient,
        tokens: AccessTokenSource,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._http = http
        self._tokens = tokens
        self._sleep = sleep

    # -- request plumbing -------------------------------------------------

    async def _send(self, build: Callable[[str], httpx.Request]) -> httpx.Response:
        refreshed = False
        for attempt in range(1, MAX_ATTEMPTS + 1):
            token = await self._tokens.get_token(force_refresh=refreshed)
            try:
                response = await self._http.send(build(token))
            except httpx.HTTPError as exc:
                if attempt == MAX_ATTEMPTS:
                    raise StorageUnavailableError("drive unreachable") from exc
                await self._backoff(attempt)
                continue
            if response.status_code == 401 and not refreshed:
                refreshed = True
                continue
            if self._retryable(response) and attempt < MAX_ATTEMPTS:
                await self._backoff(attempt)
                continue
            return response
        raise StorageUnavailableError("drive unavailable")  # pragma: no cover

    @staticmethod
    def _retryable(response: httpx.Response) -> bool:
        if response.status_code in {429, 500, 502, 503, 504}:
            return True
        return response.status_code == 403 and bool(_error_reasons(response) & _RATE_LIMIT_REASONS)

    async def _backoff(self, attempt: int) -> None:
        ceiling = min(16.0, 0.5 * 2 ** (attempt - 1))
        await self._sleep(random.uniform(0, ceiling))  # noqa: S311 - jitter, not crypto

    @staticmethod
    def _raise_for(response: httpx.Response) -> None:
        status = response.status_code
        if status < 400:
            return
        reasons = _error_reasons(response)
        if status == 401:
            raise StorageAuthError("drive authorization failed")
        if status == 404:
            raise StorageNotFoundError("item not found")
        if status == 403:
            # Google's reason codes are not sensitive and make misconfiguration diagnosable.
            logger.warning("drive_forbidden", reasons=sorted(reasons))
            if reasons & {"storageQuotaExceeded", "quotaExceeded"}:
                raise StorageQuotaExceededError("drive storage quota exceeded")
            if reasons & _API_DISABLED_REASONS:
                raise StorageApiDisabledError("drive api not enabled for this project")
            if reasons & _SCOPE_REASONS:
                raise StorageAuthError("drive scope missing; reconnect required")
            raise StoragePermissionError("drive permission denied")
        if status >= 500 or status == 429:
            raise StorageUnavailableError("drive unavailable")
        raise StorageError(f"drive request failed ({status})")

    async def _json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        def build(token: str) -> httpx.Request:
            return self._http.build_request(
                method,
                url,
                params=params,
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )

        response = await self._send(build)
        self._raise_for(response)
        payload: dict[str, Any] = response.json() if response.content else {}
        return payload

    # -- folders & metadata ----------------------------------------------

    async def ensure_root_folder(self, name: str) -> StorageItem:
        """Find (by private marker, never by name) or create Saige's own folder."""
        query = (
            f"mimeType='{FOLDER_MIME}' and trashed=false and "
            f"appProperties has {{ key='{ROOT_MARKER_KEY}' and value='{ROOT_MARKER_VALUE}' }}"
        )
        found = await self._json(
            "GET",
            f"{API}/files",
            params={"q": query, "fields": f"files({FILE_FIELDS})", "pageSize": 1},
        )
        files = found.get("files") or []
        if files:
            return to_item(files[0])
        created = await self._json(
            "POST",
            f"{API}/files",
            params={"fields": FILE_FIELDS},
            body={
                "name": name,
                "mimeType": FOLDER_MIME,
                "appProperties": {ROOT_MARKER_KEY: ROOT_MARKER_VALUE},
            },
        )
        return to_item(created)

    async def create_folder(self, name: str, parent_id: str) -> StorageItem:
        data = await self._json(
            "POST",
            f"{API}/files",
            params={"fields": FILE_FIELDS},
            body={"name": name, "mimeType": FOLDER_MIME, "parents": [check_id(parent_id)]},
        )
        return to_item(data)

    async def list_folder(
        self, folder_id: str, *, page_token: str | None = None, page_size: int = 100
    ) -> ListPage:
        params: dict[str, Any] = {
            "q": f"'{check_id(folder_id)}' in parents and trashed=false",
            "fields": f"nextPageToken,files({FILE_FIELDS})",
            "pageSize": max(1, min(page_size, 1000)),
            "orderBy": "folder,name",
        }
        if page_token:
            params["pageToken"] = page_token
        data = await self._json("GET", f"{API}/files", params=params)
        return ListPage(
            items=[to_item(f) for f in data.get("files") or []],
            next_page_token=data.get("nextPageToken"),
        )

    async def get_item(self, item_id: str) -> StorageItem:
        data = await self._json(
            "GET", f"{API}/files/{check_id(item_id)}", params={"fields": FILE_FIELDS}
        )
        return to_item(data)

    # -- content ----------------------------------------------------------

    async def upload(
        self,
        *,
        name: str,
        parent_id: str,
        mime_type: str,
        size: int,
        content: AsyncIterator[bytes],
    ) -> StorageItem:
        metadata = {"name": name, "parents": [check_id(parent_id)], "mimeType": mime_type}
        if size <= MULTIPART_LIMIT:
            data = b"".join([chunk async for chunk in content])
            if len(data) != size:
                raise StorageError("upload size mismatch")
            return await self._multipart_upload(metadata, data, mime_type)
        return await self._resumable_upload(metadata, size, mime_type, content)

    async def _multipart_upload(
        self, metadata: dict[str, Any], data: bytes, mime_type: str
    ) -> StorageItem:
        boundary = f"saige-{uuid.uuid4().hex}"
        body = (
            (
                f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                f"{json.dumps(metadata)}\r\n--{boundary}\r\nContent-Type: {mime_type}\r\n\r\n"
            ).encode()
            + data
            + f"\r\n--{boundary}--\r\n".encode()
        )

        def build(token: str) -> httpx.Request:
            return self._http.build_request(
                "POST",
                f"{UPLOAD_API}/files",
                params={"uploadType": "multipart", "fields": FILE_FIELDS},
                content=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": f"multipart/related; boundary={boundary}",
                },
            )

        response = await self._send(build)
        self._raise_for(response)
        return to_item(response.json())

    async def _resumable_upload(
        self,
        metadata: dict[str, Any],
        size: int,
        mime_type: str,
        content: AsyncIterator[bytes],
    ) -> StorageItem:
        def start(token: str) -> httpx.Request:
            return self._http.build_request(
                "POST",
                f"{UPLOAD_API}/files",
                params={"uploadType": "resumable", "fields": FILE_FIELDS},
                json=metadata,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Upload-Content-Type": mime_type,
                    "X-Upload-Content-Length": str(size),
                },
            )

        response = await self._send(start)
        self._raise_for(response)
        session_url = response.headers.get("location")
        if not session_url:
            raise StorageError("drive did not return an upload session")

        offset = 0
        buffer = bytearray()
        result: httpx.Response | None = None

        async def send_chunk(chunk: bytes, start_at: int) -> httpx.Response:
            end = start_at + len(chunk) - 1

            def build(token: str) -> httpx.Request:
                return self._http.build_request(
                    "PUT",
                    session_url,
                    content=chunk,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Range": f"bytes {start_at}-{end}/{size}",
                    },
                )

            return await self._send(build)

        async for piece in content:
            buffer.extend(piece)
            while len(buffer) >= RESUMABLE_CHUNK:
                chunk, buffer = bytes(buffer[:RESUMABLE_CHUNK]), buffer[RESUMABLE_CHUNK:]
                result = await send_chunk(chunk, offset)
                offset += len(chunk)
                if result.status_code not in (200, 201, 308):
                    self._raise_for(result)
        if buffer or offset == 0:
            result = await send_chunk(bytes(buffer), offset)
            offset += len(buffer)
        if offset != size:
            raise StorageError("upload size mismatch")
        if result is None or result.status_code not in (200, 201):
            if result is not None:
                self._raise_for(result)
            raise StorageError("upload did not complete")
        return to_item(result.json())

    async def download(self, item_id: str) -> AsyncIterator[bytes]:
        url = f"{API}/files/{check_id(item_id)}"
        refreshed = False
        for _ in range(2):
            token = await self._tokens.get_token(force_refresh=refreshed)
            request = self._http.build_request(
                "GET", url, params={"alt": "media"}, headers={"Authorization": f"Bearer {token}"}
            )
            try:
                response = await self._http.send(request, stream=True)
            except httpx.HTTPError as exc:
                raise StorageUnavailableError("drive unreachable") from exc
            try:
                if response.status_code == 401 and not refreshed:
                    refreshed = True
                    continue
                if response.status_code >= 400:
                    await response.aread()
                    self._raise_for(response)
                async for chunk in response.aiter_bytes():
                    yield chunk
                return
            finally:
                await response.aclose()
        raise StorageAuthError("drive authorization failed")

    # -- mutations --------------------------------------------------------

    async def rename(self, item_id: str, new_name: str) -> StorageItem:
        data = await self._json(
            "PATCH",
            f"{API}/files/{check_id(item_id)}",
            params={"fields": FILE_FIELDS},
            body={"name": new_name},
        )
        return to_item(data)

    async def move(self, item_id: str, new_parent_id: str) -> StorageItem:
        current = await self.get_item(item_id)
        data = await self._json(
            "PATCH",
            f"{API}/files/{check_id(item_id)}",
            params={
                "fields": FILE_FIELDS,
                "addParents": check_id(new_parent_id),
                "removeParents": ",".join(check_id(p) for p in current.parent_ids),
            },
            body={},
        )
        return to_item(data)

    async def trash(self, item_id: str) -> StorageItem:
        data = await self._json(
            "PATCH",
            f"{API}/files/{check_id(item_id)}",
            params={"fields": FILE_FIELDS},
            body={"trashed": True},
        )
        return to_item(data)

    async def restore(self, item_id: str) -> StorageItem:
        data = await self._json(
            "PATCH",
            f"{API}/files/{check_id(item_id)}",
            params={"fields": FILE_FIELDS},
            body={"trashed": False},
        )
        return to_item(data)

    async def delete_permanently(self, item_id: str) -> None:
        await self._json("DELETE", f"{API}/files/{check_id(item_id)}")

    async def list_revisions(self, item_id: str) -> list[StorageRevision]:
        data = await self._json(
            "GET",
            f"{API}/files/{check_id(item_id)}/revisions",
            params={"fields": "revisions(id,modifiedTime,size,mimeType)"},
        )
        return [
            StorageRevision(
                id=str(r["id"]),
                modified_at=_parse_time(r.get("modifiedTime")),
                size=int(r["size"]) if r.get("size") is not None else None,
                mime_type=r.get("mimeType"),
            )
            for r in data.get("revisions") or []
        ]

    # -- change detection & quota -------------------------------------------

    async def get_start_page_token(self) -> str:
        data = await self._json("GET", f"{API}/changes/startPageToken")
        return str(data["startPageToken"])

    async def list_changes(self, page_token: str) -> ChangePage:
        data = await self._json(
            "GET",
            f"{API}/changes",
            params={
                "pageToken": page_token,
                "fields": (
                    f"nextPageToken,newStartPageToken,changes(fileId,removed,file({FILE_FIELDS}))"
                ),
                "pageSize": 1000,
                "spaces": "drive",
            },
        )
        return ChangePage(
            changes=[
                StorageChange(
                    file_id=str(c["fileId"]),
                    removed=bool(c.get("removed")),
                    item=to_item(c["file"]) if c.get("file") else None,
                )
                for c in data.get("changes") or []
            ],
            next_page_token=data.get("nextPageToken"),
            new_start_page_token=data.get("newStartPageToken"),
        )

    async def quota(self) -> StorageQuota:
        data = await self._json("GET", f"{API}/about", params={"fields": "storageQuota"})
        q = data.get("storageQuota") or {}

        def num(key: str) -> int | None:
            return int(q[key]) if q.get(key) is not None else None

        return StorageQuota(
            limit_bytes=num("limit"),
            usage_bytes=num("usage") or 0,
            usage_in_drive_bytes=num("usageInDrive"),
            usage_in_trash_bytes=num("usageInDriveTrash"),
        )
