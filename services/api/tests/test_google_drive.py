from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from drive_fake import FakeDrive, StaticTokens

from saige_api.storage import google_drive as gd
from saige_api.storage.base import (
    StorageApiDisabledError,
    StorageAuthError,
    StorageNotFoundError,
    StoragePermissionError,
    StorageUnavailableError,
)
from saige_api.storage.google_drive import GoogleDriveStorageProvider


async def no_sleep(_seconds: float) -> None:
    return None


def provider(fake: FakeDrive, tokens: StaticTokens | None = None) -> GoogleDriveStorageProvider:
    return GoogleDriveStorageProvider(
        httpx.AsyncClient(transport=httpx.MockTransport(fake.handler)),
        tokens or StaticTokens("drive-access-1"),
        sleep=no_sleep,
    )


async def chunks(data: bytes, size: int = 1024 * 1024) -> AsyncIterator[bytes]:
    for i in range(0, len(data), size):
        yield data[i : i + size]


async def test_root_folder_is_created_once_and_found_by_marker() -> None:
    fake = FakeDrive()
    drive = provider(fake)
    first = await drive.ensure_root_folder("Saige Vault")
    # A folder with the same *name* made by the user is never mistaken for ours.
    fake.add("Saige Vault", "root", mime=gd.FOLDER_MIME)
    second = await drive.ensure_root_folder("Saige Vault")
    assert first.id == second.id
    assert first.is_folder
    assert sum(1 for f in fake.files.values() if f.app_properties) == 1


async def test_small_upload_list_download_round_trip() -> None:
    fake = FakeDrive()
    drive = provider(fake)
    root = await drive.ensure_root_folder("Saige Vault")
    data = b"%PDF-1.7 payslip"
    item = await drive.upload(
        name="Payslip-August-2026.pdf", parent_id=root.id, mime_type="application/pdf",
        size=len(data), content=chunks(data),
    )  # fmt: skip
    assert item.size == len(data)
    listing = await drive.list_folder(root.id)
    assert [i.name for i in listing.items] == ["Payslip-August-2026.pdf"]
    downloaded = b"".join([c async for c in drive.download(item.id)])
    assert downloaded == data


async def test_large_upload_uses_resumable_chunks() -> None:
    fake = FakeDrive()
    drive = provider(fake)
    root = await drive.ensure_root_folder("Saige Vault")
    data = bytes(range(256)) * (70 * 1024)  # ~17.5 MiB -> 3 chunks
    item = await drive.upload(
        name="scan.pdf", parent_id=root.id, mime_type="application/pdf",
        size=len(data), content=chunks(data, 3 * 1024 * 1024),
    )  # fmt: skip
    assert fake.files[item.id].content == data
    puts = [r for r in fake.requests if r.method == "PUT"]
    assert len(puts) == 3
    assert puts[0].headers["content-range"] == f"bytes 0-{gd.RESUMABLE_CHUNK - 1}/{len(data)}"


async def test_rename_move_trash_restore_delete() -> None:
    fake = FakeDrive()
    drive = provider(fake)
    root = await drive.ensure_root_folder("Saige Vault")
    career = await drive.create_folder("Career", root.id)
    fid = fake.add("Resume.pdf", root.id, b"cv")

    assert (await drive.rename(fid, "Resume-2026.pdf")).name == "Resume-2026.pdf"
    moved = await drive.move(fid, career.id)
    assert moved.parent_ids == (career.id,)
    assert (await drive.trash(fid)).trashed is True
    assert (await drive.list_folder(career.id)).items == []
    assert (await drive.restore(fid)).trashed is False
    assert [r.id for r in await drive.list_revisions(fid)] == ["r1"]
    await drive.delete_permanently(fid)
    with pytest.raises(StorageNotFoundError):
        await drive.get_item(fid)


async def test_change_detection_and_quota() -> None:
    fake = FakeDrive()
    drive = provider(fake)
    root = await drive.ensure_root_folder("Saige Vault")
    token = await drive.get_start_page_token()
    fid = fake.add("new.txt", root.id)
    await drive.rename(fid, "renamed.txt")
    page = await drive.list_changes(token)
    assert [c.file_id for c in page.changes] == [fid]
    assert page.new_start_page_token is not None
    quota = await drive.quota()
    assert quota.limit_bytes == 16106127360
    assert quota.usage_bytes == 1048576


async def test_expired_token_is_refreshed_once() -> None:
    fake = FakeDrive(valid_tokens={"fresh"})
    tokens = StaticTokens("stale", "fresh")
    drive = provider(fake, tokens)
    await drive.quota()
    assert tokens.refreshes == 1


async def test_revoked_credentials_raise_auth_error() -> None:
    fake = FakeDrive(valid_tokens=set())
    with pytest.raises(StorageAuthError):
        await provider(fake, StaticTokens("a", "b")).quota()


async def test_rate_limits_and_server_errors_are_retried() -> None:
    fake = FakeDrive(inject_statuses=[429, 403, 503])
    assert (await provider(fake).quota()).usage_bytes == 1048576


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        # What Google returns when the Drive API is disabled in the Cloud project.
        (
            {
                "code": 403,
                "errors": [{"reason": "accessNotConfigured"}],
                "details": [{"reason": "SERVICE_DISABLED"}],
            },
            StorageApiDisabledError,
        ),
        ({"details": [{"reason": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}]}, StorageAuthError),
        ({"errors": [{"reason": "forbidden"}]}, StoragePermissionError),
        ({}, StoragePermissionError),
    ],
)
async def test_forbidden_reasons_are_distinguished(
    body: dict[str, object], expected: type[Exception]
) -> None:
    transport = httpx.MockTransport(lambda _req: httpx.Response(403, json={"error": body}))
    drive = GoogleDriveStorageProvider(
        httpx.AsyncClient(transport=transport), StaticTokens("t"), sleep=no_sleep
    )
    with pytest.raises(expected):
        await drive.quota()


async def test_persistent_outage_surfaces_as_unavailable() -> None:
    fake = FakeDrive(inject_statuses=[503] * 10)
    with pytest.raises(StorageUnavailableError):
        await provider(fake).quota()


@pytest.mark.parametrize(
    "bad_id", ["x' or name contains '", "../etc", "", "a" * 300, "id with space"]
)
async def test_ids_cannot_inject_into_queries(bad_id: str) -> None:
    fake = FakeDrive()
    with pytest.raises(StorageNotFoundError):
        await provider(fake).list_folder(bad_id)
    assert fake.requests == []
