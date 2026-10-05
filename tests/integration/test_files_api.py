"""Vault file management end-to-end (real MongoDB, in-memory object store for R2)."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

import httpx
import pytest
from pymongo.asynchronous.database import AsyncDatabase

pytestmark = pytest.mark.integration

WEB = "http://web.test"
PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj << >> endobj\ntrailer\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128


def csrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("saige_csrf", "")}


async def signed_in(client: httpx.AsyncClient, *_: Any) -> None:
    email = f"files-{uuid.uuid4().hex[:8]}@example.com"
    assert (await client.post("/api/v1/auth/dev-login", json={"email": email})).status_code == 200


async def upload(
    client: httpx.AsyncClient,
    name: str = "Resume.pdf",
    data: bytes = PDF,
    folder_id: str | None = None,
) -> httpx.Response:
    form = {"folder_id": folder_id} if folder_id else {}
    return await client.post(
        "/api/v1/files",
        files={"file": (name, data, "application/octet-stream")},
        data=form,
        headers=csrf(client),
    )


async def listing(client: httpx.AsyncClient, **params: Any) -> dict[str, Any]:
    response = await client.get("/api/v1/files", params=params)
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


async def test_upload_validates_stores_and_lists(
    make_client: Any, db: AsyncDatabase[dict[str, Any]]
) -> None:
    async for client, _google, drive in make_client():
        await signed_in(client)
        response = await upload(client, "Payslip August 2026.pdf")
        assert response.status_code == 201, response.text
        body = response.json()
        # MIME type comes from content detection, not the client's claim.
        assert body["mime_type"] == "application/pdf"
        assert body["processing_status"] == "pending"
        assert body["size_bytes"] == len(PDF)

        names = [f["name"] for f in (await listing(client))["files"]]
        assert names == ["Payslip August 2026.pdf"]
        row = await db.files.find_one({"_id": uuid.UUID(body["id"])})
        assert row is not None
        assert row["checksum"] == hashlib.sha256(PDF).hexdigest()
        # R2 layout: {category}/{user_id}/{file_id}.{ext}
        assert row["object_key"] == f"documents/{row['user_id']}/{body['id']}.pdf"
        assert drive.objects[row["object_key"]][0] == PDF
        audited = await db.audit_logs.count_documents(
            {"action": "FILE_UPLOAD", "resource_id": row["_id"]}
        )
        assert audited == 1


@pytest.mark.parametrize(
    ("name", "data", "status", "code"),
    [
        ("invoice.pdf", b"MZ\x90\x00not a pdf", 415, "content_mismatch"),
        ("page.html", b"<html><script>alert(1)</script>", 415, "unsupported_type"),
        ("empty.pdf", b"", 400, "empty_file"),
    ],
)
async def test_upload_rejections_store_nothing(
    make_client: Any, name: str, data: bytes, status: int, code: str
) -> None:
    async for client, _google, drive in make_client():
        await signed_in(client)
        before = set(drive.objects)
        response = await upload(client, name, data)
        assert response.status_code == status, response.text
        assert response.json()["error"]["code"] == code
        assert set(drive.objects) == before
        assert (await listing(client))["total"] == 0


async def test_upload_size_limit_enforced_before_reading(make_client: Any) -> None:
    async for client, _google, _drive in make_client(max_upload_bytes=1024):
        await signed_in(client)
        response = await upload(client, "big.pdf", PDF + b"\x00" * (200 * 1024))
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "file_too_large"


async def test_upload_requires_configured_storage(make_client: Any) -> None:
    async for client, _google, _drive in make_client(storage=False):
        await client.post("/api/v1/auth/dev-login", json={"email": "nostorage@example.com"})
        response = await upload(client)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "storage_not_configured"


async def test_download_and_preview_headers(make_client: Any) -> None:
    async for client, _google, _drive in make_client():
        await signed_in(client)
        pdf_id = (await upload(client, "Résumé 2026.pdf")).json()["id"]
        text_id = (await upload(client, "notes.md", b"# <script>alert(1)</script>")).json()["id"]

        download = await client.get(f"/api/v1/files/{pdf_id}/content")
        assert download.status_code == 200
        assert download.content == PDF
        assert download.headers["content-disposition"].startswith("attachment;")
        assert (
            "filename*=UTF-8''R%C3%A9sum%C3%A9%202026.pdf"
            in download.headers["content-disposition"]
        )
        assert download.headers["content-security-policy"].startswith("sandbox")
        assert download.headers["x-content-type-options"] == "nosniff"
        assert download.headers["cache-control"] == "private, no-store"

        preview = await client.get(f"/api/v1/files/{pdf_id}/content", params={"inline": "true"})
        assert preview.headers["content-disposition"].startswith("inline;")
        assert preview.headers["content-type"] == "application/pdf"

        markdown = await client.get(f"/api/v1/files/{text_id}/content", params={"inline": "true"})
        assert markdown.headers["content-type"] == "text/plain; charset=utf-8"


async def test_folders_breadcrumbs_and_moves(make_client: Any) -> None:
    async for client, _google, _drive in make_client():
        await signed_in(client)
        career = (
            await client.post("/api/v1/folders", json={"name": "Career"}, headers=csrf(client))
        ).json()
        offers = (
            await client.post(
                "/api/v1/folders",
                json={"name": "Offers", "parent_id": career["id"]},
                headers=csrf(client),
            )
        ).json()
        file_id = (await upload(client, "Offer.pdf", folder_id=offers["id"])).json()["id"]

        inside = await listing(client, folder_id=offers["id"])
        assert [b["name"] for b in inside["breadcrumbs"]] == ["My Vault", "Career", "Offers"]
        assert [f["name"] for f in inside["files"]] == ["Offer.pdf"]
        root = await listing(client)
        assert [f["name"] for f in root["folders"]] == ["Career"] and root["files"] == []

        # Rename keeps the validated extension; move to root.
        renamed = await client.patch(
            f"/api/v1/files/{file_id}", json={"name": "Offer Letter", "move_to_root": True},
            headers=csrf(client),
        )  # fmt: skip
        assert renamed.json()["name"] == "Offer Letter.pdf"
        assert renamed.json()["folder_id"] is None

        cycle = await client.patch(
            f"/api/v1/folders/{career['id']}",
            json={"parent_id": offers["id"]},
            headers=csrf(client),
        )
        assert cycle.status_code == 409
        not_empty = await client.delete(f"/api/v1/folders/{career['id']}", headers=csrf(client))
        assert not_empty.status_code == 409
        assert (
            await client.delete(f"/api/v1/folders/{offers['id']}", headers=csrf(client))
        ).status_code == 204
        assert (
            await client.delete(f"/api/v1/folders/{career['id']}", headers=csrf(client))
        ).status_code == 204


async def test_trash_restore_and_permanent_delete(make_client: Any) -> None:
    async for client, _google, drive in make_client():
        await signed_in(client)
        file_id = (await upload(client)).json()["id"]
        stored = set(drive.objects)
        assert len(stored) == 1

        early = await client.delete(f"/api/v1/files/{file_id}/permanent", headers=csrf(client))
        assert early.status_code == 409  # must be trashed first
        assert (
            await client.delete(f"/api/v1/files/{file_id}", headers=csrf(client))
        ).status_code == 204
        assert (await listing(client))["total"] == 0
        trashed = await listing(client, trashed="true")
        assert [f["id"] for f in trashed["files"]] == [file_id]
        assert set(drive.objects) == stored  # trash keeps content

        restored = await client.post(f"/api/v1/files/{file_id}/restore", headers=csrf(client))
        assert restored.status_code == 200 and restored.json()["deleted_at"] is None
        await client.delete(f"/api/v1/files/{file_id}", headers=csrf(client))
        gone = await client.delete(f"/api/v1/files/{file_id}/permanent", headers=csrf(client))
        assert gone.status_code == 204
        assert not drive.objects  # permanent delete removes it from storage
        assert (await client.get(f"/api/v1/files/{file_id}")).status_code == 404


async def test_star_classify_tag_and_filter(make_client: Any) -> None:
    async for client, _google, _drive in make_client():
        await signed_in(client)
        a = (await upload(client, "Resume.pdf")).json()["id"]
        b = (await upload(client, "shot.png", PNG)).json()["id"]
        assert (await client.get(f"/api/v1/files/{b}")).json()["document_type"] == "image"

        await client.patch(
            f"/api/v1/files/{a}",
            json={"is_starred": True, "document_type": "resume"},
            headers=csrf(client),
        )
        file_a = (await client.get(f"/api/v1/files/{a}")).json()
        assert file_a["is_starred"] is True
        assert file_a["document_type"] == "resume" and file_a["document_type_source"] == "user"

        tagged = await client.put(
            f"/api/v1/files/{a}/tags",
            json={"names": ["Career", "#selenium", "career"]},
            headers=csrf(client),
        )
        assert sorted(t["name"] for t in tagged.json()["tags"]) == ["Career", "selenium"]

        assert [f["id"] for f in (await listing(client, starred="true"))["files"]] == [a]
        assert [f["id"] for f in (await listing(client, tag="Selenium"))["files"]] == [a]
        assert [f["id"] for f in (await listing(client, type="image"))["files"]] == [b]
        assert [f["id"] for f in (await listing(client, document_type="resume"))["files"]] == [a]
        assert [f["id"] for f in (await listing(client, q="resu"))["files"]] == [a]
        assert (await listing(client, q="%"))["total"] == 0  # wildcards are literal
        tags = (await client.get("/api/v1/tags")).json()["tags"]
        assert sorted(t["name"] for t in tags) == ["Career", "selenium"]

        stats = (await client.get("/api/v1/files/stats")).json()
        assert stats["total_files"] == 2 and stats["images"] == 1 and stats["pdfs"] == 1
        assert stats["starred"] == 1 and stats["pending_processing"] == 2


async def test_collections(make_client: Any) -> None:
    async for client, _google, _drive in make_client():
        await signed_in(client)
        f1 = (await upload(client, "Degree.pdf")).json()["id"]
        f2 = (await upload(client, "Diploma.pdf")).json()["id"]
        made = await client.post(
            "/api/v1/collections", json={"name": "Education"}, headers=csrf(client)
        )
        assert made.status_code == 201
        cid = made.json()["id"]
        dup = await client.post(
            "/api/v1/collections", json={"name": "education"}, headers=csrf(client)
        )
        assert dup.status_code == 409

        added = await client.post(
            f"/api/v1/collections/{cid}/files",
            json={"file_ids": [f1, f2, f1]},
            headers=csrf(client),
        )
        assert added.json()["file_count"] == 2
        detail = (await client.get(f"/api/v1/collections/{cid}")).json()
        assert [f["name"] for f in detail["files"]] == ["Degree.pdf", "Diploma.pdf"]
        in_collection = (await listing(client, collection_id=cid))["files"]
        assert sorted(f["id"] for f in in_collection) == sorted([f1, f2])

        removed = await client.delete(f"/api/v1/collections/{cid}/files/{f2}", headers=csrf(client))
        assert removed.status_code == 204
        assert (
            await client.delete(f"/api/v1/collections/{cid}", headers=csrf(client))
        ).status_code == 204
        # Deleting a collection never deletes files.
        assert (await listing(client))["total"] == 2


async def test_bulk_actions_skip_foreign_files(make_client: Any) -> None:
    async for client, _google, _drive in make_client():
        await signed_in(client)
        ids = [(await upload(client, f"doc{i}.pdf")).json()["id"] for i in range(3)]
        foreign = str(uuid.uuid4())
        result = await client.post(
            "/api/v1/files/bulk",
            json={"file_ids": [*ids, foreign], "action": "star"},
            headers=csrf(client),
        )
        assert sorted(result.json()["succeeded"]) == sorted(ids)
        assert result.json()["failed"] == [foreign]
        trashed = await client.post(
            "/api/v1/files/bulk",
            json={"file_ids": ids[:2], "action": "trash"},
            headers=csrf(client),
        )
        assert len(trashed.json()["succeeded"]) == 2
        assert (await listing(client))["total"] == 1


async def test_other_users_cannot_touch_my_files(make_client: Any) -> None:
    async for client, google, _drive in make_client():
        await signed_in(client)
        file_id = (await upload(client)).json()["id"]
        folder_id = (
            await client.post("/api/v1/folders", json={"name": "Private"}, headers=csrf(client))
        ).json()["id"]
        cid = (
            await client.post("/api/v1/collections", json={"name": "Mine"}, headers=csrf(client))
        ).json()["id"]

        intruder = httpx.AsyncClient(transport=client._transport, base_url=WEB)
        await signed_in(intruder, google)
        h = csrf(intruder)
        checks = [
            await intruder.get(f"/api/v1/files/{file_id}"),
            await intruder.get(f"/api/v1/files/{file_id}/content"),
            await intruder.patch(f"/api/v1/files/{file_id}", json={"name": "pwned"}, headers=h),
            await intruder.delete(f"/api/v1/files/{file_id}", headers=h),
            await intruder.put(f"/api/v1/files/{file_id}/tags", json={"names": ["x"]}, headers=h),
            await intruder.get("/api/v1/files", params={"folder_id": folder_id}),
            await intruder.get(f"/api/v1/collections/{cid}"),
        ]
        assert [r.status_code for r in checks] == [404] * len(checks)
        # Uploading into someone else's folder is refused too.
        assert (await upload(intruder, folder_id=folder_id)).status_code == 404
        # Adding a foreign file to one's own collection silently adds nothing.
        own = (
            await intruder.post("/api/v1/collections", json={"name": "Theirs"}, headers=h)
        ).json()["id"]
        added = await intruder.post(
            f"/api/v1/collections/{own}/files", json={"file_ids": [file_id]}, headers=h
        )
        assert added.json()["file_count"] == 0
        assert (await listing(intruder))["total"] == 0
        await intruder.aclose()

        mine = (await client.get(f"/api/v1/files/{file_id}")).json()
        assert mine["name"] == "Resume.pdf" and mine["deleted_at"] is None


async def test_mutations_require_csrf(make_client: Any) -> None:
    async for client, _google, _drive in make_client():
        await signed_in(client)
        file_id = (await upload(client)).json()["id"]
        no_csrf = [
            await client.post("/api/v1/files", files={"file": ("a.pdf", PDF, "application/pdf")}),
            await client.patch(f"/api/v1/files/{file_id}", json={"is_starred": True}),
            await client.delete(f"/api/v1/files/{file_id}"),
        ]
        assert [r.status_code for r in no_csrf] == [403, 403, 403]
