"""In-memory fake of the Google Drive v3 REST API (the subset Saige uses)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

FOLDER = "application/vnd.google-apps.folder"


@dataclass
class FakeFile:
    id: str
    name: str
    mime_type: str
    parents: list[str]
    content: bytes = b""
    trashed: bool = False
    app_properties: dict[str, str] = field(default_factory=dict)
    revisions: list[str] = field(default_factory=list)
    modified: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def resource(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "mimeType": self.mime_type,
            "parents": self.parents,
            "trashed": self.trashed,
            "modifiedTime": self.modified,
            "headRevisionId": self.revisions[-1] if self.revisions else None,
        }
        if self.mime_type != FOLDER:
            data["size"] = str(len(self.content))
        return data


@dataclass
class FakeDrive:
    valid_tokens: set[str] = field(default_factory=lambda: {"drive-access-1"})
    files: dict[str, FakeFile] = field(default_factory=dict)
    # Status codes to return (in order) before serving requests normally.
    inject_statuses: list[int] = field(default_factory=list)
    requests: list[httpx.Request] = field(default_factory=list)
    uploads: dict[str, dict[str, Any]] = field(default_factory=dict)
    change_log: list[dict[str, Any]] = field(default_factory=list)

    def _new_id(self) -> str:
        return uuid.uuid4().hex[:20]

    def _record(self, f: FakeFile, removed: bool = False) -> None:
        self.change_log.append({"fileId": f.id, "removed": removed, "file": f.resource()})

    def add(self, name: str, parent: str, content: bytes = b"", mime: str = "text/plain") -> str:
        fid = self._new_id()
        self.files[fid] = FakeFile(fid, name, mime, [parent], content, revisions=["r1"])
        return fid

    def handles(self, url: str) -> bool:
        return "googleapis.com/drive/v3" in url or "googleapis.com/upload/drive/v3" in url

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        auth = request.headers.get("authorization", "")
        if auth.removeprefix("Bearer ") not in self.valid_tokens:
            return httpx.Response(
                401, json={"error": {"code": 401, "errors": [{"reason": "authError"}]}}
            )
        if self.inject_statuses:
            status = self.inject_statuses.pop(0)
            reason = "rateLimitExceeded" if status == 403 else "backendError"
            return httpx.Response(status, json={"error": {"errors": [{"reason": reason}]}})

        url = urlparse(str(request.url))
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        path = url.path
        if path.startswith("/upload/drive/v3/files"):
            return self._upload(request, params)
        if path.startswith("/upload/session/"):
            return self._resume(request, path.rsplit("/", 1)[1])
        path = path.removeprefix("/drive/v3")

        if path == "/about":
            return httpx.Response(
                200,
                json={
                    "storageQuota": {
                        "limit": "16106127360",
                        "usage": "1048576",
                        "usageInDrive": "524288",
                        "usageInDriveTrash": "0",
                    }
                },
            )
        if path == "/changes/startPageToken":
            return httpx.Response(200, json={"startPageToken": str(len(self.change_log))})
        if path == "/changes":
            start = int(params["pageToken"])
            return httpx.Response(
                200,
                json={
                    "changes": self.change_log[start:],
                    "newStartPageToken": str(len(self.change_log)),
                },
            )
        if path == "/files" and request.method == "GET":
            return self._list(params.get("q", ""))
        if path == "/files" and request.method == "POST":
            body = json.loads(request.content or b"{}")
            fid = self._new_id()
            f = FakeFile(
                fid,
                body["name"],
                body.get("mimeType", "application/octet-stream"),
                body.get("parents", ["root"]),
                app_properties=body.get("appProperties", {}),
            )
            self.files[fid] = f
            self._record(f)
            return httpx.Response(200, json=f.resource())

        match = re.fullmatch(r"/files/([^/]+)(/revisions)?", path)
        if not match:
            return httpx.Response(404)
        f = self.files.get(match.group(1))
        if f is None:
            return httpx.Response(404, json={"error": {"errors": [{"reason": "notFound"}]}})
        if match.group(2):
            return httpx.Response(
                200,
                json={
                    "revisions": [
                        {"id": r, "modifiedTime": f.modified, "size": str(len(f.content))}
                        for r in f.revisions
                    ]
                },
            )
        if request.method == "GET" and params.get("alt") == "media":
            return httpx.Response(200, content=f.content)
        if request.method == "GET":
            return httpx.Response(200, json=f.resource())
        if request.method == "PATCH":
            body = json.loads(request.content or b"{}")
            if "name" in body:
                f.name = body["name"]
            if "trashed" in body:
                f.trashed = bool(body["trashed"])
            if "addParents" in params:
                removed = set(params.get("removeParents", "").split(","))
                f.parents = [p for p in f.parents if p not in removed] + [params["addParents"]]
            self._record(f)
            return httpx.Response(200, json=f.resource())
        if request.method == "DELETE":
            del self.files[f.id]
            self._record(f, removed=True)
            return httpx.Response(204)
        return httpx.Response(405)

    def _list(self, q: str) -> httpx.Response:
        if "appProperties has" in q:
            key, value = re.search(r"key='([^']+)' and value='([^']+)'", q).groups()  # type: ignore[union-attr]
            items = [
                f for f in self.files.values()
                if f.app_properties.get(key) == value and not f.trashed and f.mime_type == FOLDER
            ]  # fmt: skip
        else:
            parent = re.match(r"'([^']+)' in parents", q).group(1)  # type: ignore[union-attr]
            items = [f for f in self.files.values() if parent in f.parents and not f.trashed]
        return httpx.Response(200, json={"files": [f.resource() for f in items]})

    def _upload(self, request: httpx.Request, params: dict[str, str]) -> httpx.Response:
        if params.get("uploadType") == "multipart":
            boundary = request.headers["content-type"].split("boundary=")[1]
            parts = request.content.split(f"--{boundary}".encode())
            meta = json.loads(parts[1].split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n"))
            data = parts[2].split(b"\r\n\r\n", 1)[1].removesuffix(b"\r\n")
            return self._store(meta, data)
        sid = uuid.uuid4().hex
        self.uploads[sid] = {
            "meta": json.loads(request.content),
            "size": int(request.headers["x-upload-content-length"]),
            "data": bytearray(),
        }
        return httpx.Response(
            200, headers={"location": f"https://www.googleapis.com/upload/session/{sid}"}
        )

    def _resume(self, request: httpx.Request, sid: str) -> httpx.Response:
        session = self.uploads[sid]
        session["data"].extend(request.content)
        if len(session["data"]) < session["size"]:
            return httpx.Response(308, headers={"range": f"bytes=0-{len(session['data']) - 1}"})
        return self._store(session["meta"], bytes(session["data"]))

    def _store(self, meta: dict[str, Any], data: bytes) -> httpx.Response:
        fid = self._new_id()
        f = FakeFile(
            fid,
            meta["name"],
            meta.get("mimeType", "application/octet-stream"),
            meta["parents"],
            data,
            revisions=["r1"],
        )
        self.files[fid] = f
        self._record(f)
        return httpx.Response(200, json=f.resource())


class StaticTokens:
    """AccessTokenSource for unit tests: hands out tokens from a list."""

    def __init__(self, *tokens: str) -> None:
        self._tokens = list(tokens)
        self.refreshes = 0

    async def get_token(self, *, force_refresh: bool = False) -> str:
        if force_refresh and len(self._tokens) > 1:
            self.refreshes += 1
            self._tokens.pop(0)
        return self._tokens[0]
