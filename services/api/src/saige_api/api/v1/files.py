"""/api/v1/files, /folders, /tags, /collections — vault file management."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile

from saige_api.api.deps import DbDep, ResourcesDep
from saige_api.audit import record_audit
from saige_api.auth.deps import AuthContext, CurrentUserDep
from saige_api.core.errors import AppError
from saige_api.db import Doc
from saige_api.enums import AuditAction, DocumentType
from saige_api.files.service import CATEGORIES, FileFilters, StorageNotConnectedError, VaultService
from saige_api.files.validation import UploadRejectedError, sanitize_filename, validate_upload
from saige_api.resources import Resources
from saige_api.schemas.files import (
    Breadcrumb,
    BulkRequest,
    BulkResult,
    CollectionCreate,
    CollectionDetail,
    CollectionFilesUpdate,
    CollectionListResponse,
    CollectionSummary,
    CollectionUpdate,
    FileListResponse,
    FileStats,
    FileSummary,
    FileUpdate,
    FolderCreate,
    FolderSummary,
    FolderUpdate,
    SortKey,
    TagListResponse,
    TagRef,
    TagsUpdate,
    TypeGroup,
)
from saige_api.schemas.system import ErrorResponse
from saige_api.storage.base import ObjectStore, StorageError

router = APIRouter(tags=["files"])

ERRORS: dict[int | str, dict[str, object]] = {
    code: {"model": ErrorResponse} for code in (400, 401, 403, 404, 409, 413, 415, 429, 503)
}
INLINE_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg", "image/webp", "image/gif"})
TEXT_TYPES = frozenset(
    {"text/plain", "text/markdown", "text/csv", "application/json", "application/xml"}
)
MULTIPART_OVERHEAD = 64 * 1024
# Even if a file were navigated to directly, it gets no script and no origin.
CONTENT_CSP = "sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"


class UploadError(AppError):
    def __init__(self, rejected: UploadRejectedError) -> None:
        super().__init__(rejected.message)
        self.code = rejected.code
        self.status_code = {
            "file_too_large": status.HTTP_413_CONTENT_TOO_LARGE,
            "unsupported_type": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "content_mismatch": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "unsupported_encoding": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        }.get(rejected.code, status.HTTP_400_BAD_REQUEST)


# -- helpers -------------------------------------------------------------------


def _tag(tag: Doc) -> TagRef:
    return TagRef(id=tag.id, name=tag.name, color=tag.color)


def _file(file: Doc, tags: Sequence[Doc] = ()) -> FileSummary:
    return FileSummary(
        id=file.id,
        name=file.name,
        extension=file.extension,
        mime_type=file.mime_type,
        size_bytes=file.size_bytes,
        folder_id=file.folder_id,
        document_type=file.document_type,
        document_type_source=file.document_type_source,
        is_starred=file.is_starred,
        processing_status=file.processing_status,
        created_at=file.created_at,
        updated_at=file.updated_at,
        deleted_at=file.deleted_at,
        last_accessed_at=file.last_accessed_at,
        tags=[_tag(t) for t in tags],
        category=file.category,
    )


def _folder(folder: Doc) -> FolderSummary:
    return FolderSummary(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


def _collection(row: Doc, count: int) -> CollectionSummary:
    return CollectionSummary(
        id=row.id, name=row.name, description=row.description, color=row.color, icon=row.icon,
        file_count=count, created_at=row.created_at, updated_at=row.updated_at,
    )  # fmt: skip


async def _files_with_tags(service: VaultService, files: Sequence[Doc]) -> list[FileSummary]:
    tags = await service.tags_for(files)
    return [_file(f, tags.get(f.id, [])) for f in files]


def _objects(resources: Resources) -> ObjectStore:
    if resources.objects is None:
        raise StorageNotConnectedError(
            "File storage isn't configured on this server (Cloudflare R2 settings are missing)."
        )
    return resources.objects


async def _audit(
    request: Request,
    service: VaultService,
    action: AuditAction,
    file_id: uuid.UUID,
    **details: object,
) -> None:
    await record_audit(
        service.db, request, action, user_id=service.user_id, resource_type="file",
        resource_id=file_id, details=details or None,
    )  # fmt: skip


def vault(auth: AuthContext, db: DbDep) -> VaultService:
    return VaultService(db, auth.user_id)


# -- listing -------------------------------------------------------------------


@router.get("/files", response_model=FileListResponse, summary="List files", responses=ERRORS)
async def list_files(
    auth: CurrentUserDep,
    db: DbDep,
    folder_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    type: TypeGroup | None = None,
    document_type: DocumentType | None = None,
    starred: bool | None = None,
    trashed: bool = False,
    tag: Annotated[str | None, Query(max_length=64)] = None,
    collection_id: uuid.UUID | None = None,
    all_folders: bool = False,
    sort: SortKey = "updated",
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FileListResponse:
    service = vault(auth, db)
    folder = await service.get_folder(folder_id) if folder_id else None
    filters = FileFilters(
        folder_id=folder_id, all_folders=all_folders, query=q, type_group=type,
        document_type=document_type, starred=starred, trashed=trashed, tag=tag,
        collection_id=collection_id, sort=sort, descending=order == "desc",
        limit=limit, offset=offset,
    )  # fmt: skip
    files, total = await service.list_files(filters)
    browsing = not any([q, type, document_type, starred, tag, collection_id, trashed, all_folders])
    folders = await service.list_subfolders(folder_id) if browsing and offset == 0 else []
    return FileListResponse(
        folders=[_folder(f) for f in folders],
        files=await _files_with_tags(service, files),
        total=total,
        breadcrumbs=[Breadcrumb(id=i, name=n) for i, n in await service.breadcrumbs(folder)],
    )


@router.get("/files/stats", response_model=FileStats, summary="Vault statistics", responses=ERRORS)
async def file_stats(auth: CurrentUserDep, db: DbDep) -> FileStats:
    return FileStats.model_validate(await vault(auth, db).stats())


@router.get("/files/{file_id}", response_model=FileSummary, summary="Get a file", responses=ERRORS)
async def get_file(file_id: uuid.UUID, auth: CurrentUserDep, db: DbDep) -> FileSummary:
    service = vault(auth, db)
    file = await service.get_file(file_id, include_trashed=True)
    return (await _files_with_tags(service, [file]))[0]


# -- upload & content --------------------------------------------------------------


@router.post(
    "/files",
    response_model=FileSummary,
    status_code=201,
    summary="Upload a file (multipart/form-data: file, folder_id?, category?)",
    responses=ERRORS,
)
async def upload_file(
    request: Request, auth: CurrentUserDep, resources: ResourcesDep, db: DbDep
) -> FileSummary:
    max_bytes = resources.settings.max_upload_bytes
    declared = request.headers.get("content-length")
    if declared is None:
        raise AppError("A Content-Length header is required for uploads.")
    if not declared.isdigit() or int(declared) > max_bytes + MULTIPART_OVERHEAD:
        raise UploadError(
            UploadRejectedError(
                "file_too_large", f"Files can be at most {max_bytes // (1024 * 1024)} MB."
            )
        )
    await resources.rate_limiter.hit(
        "upload", str(auth.user_id), limit=resources.settings.upload_rate_limit_per_minute
    )
    service = vault(auth, db)
    objects = _objects(resources)  # fail before reading the body

    form = await request.form(max_files=1, max_fields=4)
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise AppError("Attach the file in a form field named 'file'.")
    raw_folder = form.get("folder_id")
    try:
        folder_id = uuid.UUID(raw_folder) if isinstance(raw_folder, str) and raw_folder else None
    except ValueError as exc:
        raise AppError("folder_id must be a UUID") from exc
    raw_category = form.get("category")
    category = raw_category if isinstance(raw_category, str) and raw_category else None
    if category is not None and category not in CATEGORIES:
        raise AppError(f"category must be one of: {', '.join(CATEGORIES)}")

    try:
        name = sanitize_filename(upload.filename)
        size = upload.size if upload.size is not None else len(await upload.read())
        try:
            kind = validate_upload(name, upload.file, size, max_bytes=max_bytes)
        except UploadRejectedError as rejected:
            raise UploadError(rejected) from rejected
        file = await service.upload(
            objects, stream=upload.file, size=size, filename=name, kind=kind,
            folder_id=folder_id, category=category,
        )  # fmt: skip
    finally:
        await upload.close()
    await _audit(request, service, AuditAction.FILE_UPLOAD, file.id, size=size, type=kind.extension)
    return _file(file)


def _content_disposition(name: str, inline: bool) -> str:
    ascii_name = name.encode("ascii", "replace").decode().replace('"', "_").replace("?", "_")
    disposition = "inline" if inline else "attachment"
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


@router.get(
    "/files/{file_id}/content",
    summary="Download or preview file content",
    responses={200: {"content": {"application/octet-stream": {}}}, **ERRORS},
)
async def file_content(
    file_id: uuid.UUID,
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: DbDep,
    inline: bool = False,
) -> StreamingResponse:
    service = vault(auth, db)
    file = await service.get_file(file_id)
    chunks = _objects(resources).get(file.object_key).__aiter__()
    try:
        first = await chunks.__anext__()  # surface storage errors before headers are sent
    except StopAsyncIteration:
        first = b""

    async def body() -> AsyncIterator[bytes]:
        yield first
        async for chunk in chunks:
            yield chunk

    is_text = file.mime_type in TEXT_TYPES
    show_inline = inline and (file.mime_type in INLINE_TYPES or is_text)
    # Text is always served as text/plain so browsers never interpret it.
    media_type = "text/plain; charset=utf-8" if is_text else file.mime_type
    await service.record_access(file)
    await _audit(request, service, AuditAction.FILE_DOWNLOAD, file.id, inline=show_inline)
    return StreamingResponse(
        body(),
        media_type=media_type,
        headers={
            "Content-Disposition": _content_disposition(file.name, show_inline),
            "Content-Length": str(file.size_bytes),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": CONTENT_CSP,
        },
    )


# -- mutations --------------------------------------------------------------------


@router.patch(
    "/files/{file_id}",
    response_model=FileSummary,
    summary="Rename, move, star or reclassify a file",
    responses=ERRORS,
)
async def update_file(
    file_id: uuid.UUID,
    body: FileUpdate,
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: DbDep,
) -> FileSummary:
    service = vault(auth, db)
    file = await service.get_file(file_id)
    changed = await service.update_file(
        file, name=body.name, folder_id=body.folder_id, move_to_root=body.move_to_root,
        is_starred=body.is_starred, document_type=body.document_type,
    )  # fmt: skip
    if "rename" in changed:
        await _audit(request, service, AuditAction.FILE_RENAME, file.id)
    if "move" in changed:
        await _audit(request, service, AuditAction.FILE_MOVE, file.id)
    return (await _files_with_tags(service, [file]))[0]


@router.delete(
    "/files/{file_id}", status_code=204, summary="Move a file to trash", responses=ERRORS
)
async def trash_file(
    file_id: uuid.UUID,
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: DbDep,
) -> Response:
    service = vault(auth, db)
    file = await service.get_file(file_id)
    await service.trash(file)
    await _audit(request, service, AuditAction.FILE_DELETE, file.id, permanent=False)
    return Response(status_code=204)


@router.post(
    "/files/{file_id}/restore",
    response_model=FileSummary,
    summary="Restore from trash",
    responses=ERRORS,
)
async def restore_file(
    file_id: uuid.UUID,
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: DbDep,
) -> FileSummary:
    service = vault(auth, db)
    file = await service.get_file(file_id, include_trashed=True)
    await service.restore(file)
    await _audit(request, service, AuditAction.FILE_RESTORE, file.id)
    return (await _files_with_tags(service, [file]))[0]


@router.delete(
    "/files/{file_id}/permanent",
    status_code=204,
    summary="Permanently delete a trashed file (from storage too)",
    responses=ERRORS,
)
async def delete_file_permanently(
    file_id: uuid.UUID,
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: DbDep,
) -> Response:
    service = vault(auth, db)
    file = await service.get_file(file_id, include_trashed=True)
    await _audit(request, service, AuditAction.FILE_DELETE, file.id, permanent=True)
    await service.delete_permanently(resources.objects, file)
    return Response(status_code=204)


@router.post(
    "/files/bulk", response_model=BulkResult, summary="Bulk file actions", responses=ERRORS
)
async def bulk(
    body: BulkRequest,
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: DbDep,
) -> BulkResult:
    service = vault(auth, db)
    succeeded: list[uuid.UUID] = []
    failed: list[uuid.UUID] = []
    for file_id in dict.fromkeys(body.file_ids):
        try:
            file = await service.get_file(file_id, include_trashed=body.action == "restore")
            if body.action == "trash":
                await service.trash(file)
                await _audit(
                    request, service, AuditAction.FILE_DELETE, file.id, permanent=False, bulk=True
                )
            elif body.action == "restore":
                await service.restore(file)
                await _audit(request, service, AuditAction.FILE_RESTORE, file.id, bulk=True)
            elif body.action in ("star", "unstar"):
                await service.update_file(file, is_starred=body.action == "star")
            elif body.action == "move":
                await service.update_file(
                    file, folder_id=body.folder_id, move_to_root=body.folder_id is None
                )
                await _audit(request, service, AuditAction.FILE_MOVE, file.id, bulk=True)
            succeeded.append(file_id)
        except (AppError, StorageError):
            failed.append(file_id)
    return BulkResult(succeeded=succeeded, failed=failed)


@router.put(
    "/files/{file_id}/tags",
    response_model=FileSummary,
    summary="Replace a file's tags",
    responses=ERRORS,
)
async def set_tags(
    file_id: uuid.UUID, body: TagsUpdate, auth: CurrentUserDep, db: DbDep
) -> FileSummary:
    service = vault(auth, db)
    file = await service.get_file(file_id)
    await service.set_file_tags(file, body.names)
    return (await _files_with_tags(service, [file]))[0]


# -- folders ------------------------------------------------------------------------


@router.post(
    "/folders",
    response_model=FolderSummary,
    status_code=201,
    summary="Create a folder",
    responses=ERRORS,
)
async def create_folder(
    body: FolderCreate, auth: CurrentUserDep, resources: ResourcesDep, db: DbDep
) -> FolderSummary:
    folder = await vault(auth, db).create_folder(body.name, body.parent_id)
    return _folder(folder)


@router.patch(
    "/folders/{folder_id}",
    response_model=FolderSummary,
    summary="Rename or move a folder",
    responses=ERRORS,
)
async def update_folder(
    folder_id: uuid.UUID,
    body: FolderUpdate,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: DbDep,
) -> FolderSummary:
    service = vault(auth, db)
    folder = await service.get_folder(folder_id)
    await service.update_folder(
        folder,
        name=body.name, parent_id=body.parent_id, move_to_root=body.move_to_root,
    )  # fmt: skip
    return _folder(folder)


@router.delete(
    "/folders/{folder_id}", status_code=204, summary="Delete an empty folder", responses=ERRORS
)
async def delete_folder(
    folder_id: uuid.UUID, auth: CurrentUserDep, resources: ResourcesDep, db: DbDep
) -> Response:
    service = vault(auth, db)
    folder = await service.get_folder(folder_id)
    await service.delete_folder(folder)
    return Response(status_code=204)


# -- tags ------------------------------------------------------------------------------


@router.get("/tags", response_model=TagListResponse, summary="List your tags", responses=ERRORS)
async def list_tags(auth: CurrentUserDep, db: DbDep) -> TagListResponse:
    return TagListResponse(tags=[_tag(t) for t in await vault(auth, db).list_tags()])


@router.delete("/tags/{tag_id}", status_code=204, summary="Delete a tag", responses=ERRORS)
async def delete_tag(tag_id: uuid.UUID, auth: CurrentUserDep, db: DbDep) -> Response:
    await vault(auth, db).delete_tag(tag_id)
    return Response(status_code=204)


# -- collections ----------------------------------------------------------------------


@router.get(
    "/collections",
    response_model=CollectionListResponse,
    summary="List collections",
    responses=ERRORS,
)
async def list_collections(auth: CurrentUserDep, db: DbDep) -> CollectionListResponse:
    rows = await vault(auth, db).list_collections()
    return CollectionListResponse(collections=[_collection(c, n) for c, n in rows])


@router.post(
    "/collections",
    response_model=CollectionSummary,
    status_code=201,
    summary="Create a collection",
    responses=ERRORS,
)
async def create_collection(
    body: CollectionCreate, auth: CurrentUserDep, db: DbDep
) -> CollectionSummary:
    row = await vault(auth, db).create_collection(
        body.name, body.description, body.color, body.icon
    )
    return _collection(row, 0)


@router.get(
    "/collections/{collection_id}",
    response_model=CollectionDetail,
    summary="Collection with its files",
    responses=ERRORS,
)
async def get_collection(
    collection_id: uuid.UUID, auth: CurrentUserDep, db: DbDep
) -> CollectionDetail:
    service = vault(auth, db)
    row = await service.get_collection(collection_id)
    files, total = await service.list_files(
        FileFilters(collection_id=row.id, sort="name", descending=False, limit=500)
    )
    return CollectionDetail(
        collection=_collection(row, total), files=await _files_with_tags(service, files)
    )


@router.patch(
    "/collections/{collection_id}",
    response_model=CollectionSummary,
    summary="Update a collection",
    responses=ERRORS,
)
async def update_collection(
    collection_id: uuid.UUID, body: CollectionUpdate, auth: CurrentUserDep, db: DbDep
) -> CollectionSummary:
    service = vault(auth, db)
    row = await service.get_collection(collection_id)
    updates = {
        field: value.strip() if isinstance(value, str) else value
        for field in ("name", "description", "color")
        if (value := getattr(body, field)) is not None
    }
    await service.update_collection(row, updates)
    return _collection(row, await service.collection_count(row))


@router.delete(
    "/collections/{collection_id}",
    status_code=204,
    summary="Delete a collection (files are kept)",
    responses=ERRORS,
)
async def delete_collection(collection_id: uuid.UUID, auth: CurrentUserDep, db: DbDep) -> Response:
    service = vault(auth, db)
    await service.delete_collection(await service.get_collection(collection_id))
    return Response(status_code=204)


@router.post(
    "/collections/{collection_id}/files",
    response_model=CollectionSummary,
    summary="Add files to a collection",
    responses=ERRORS,
)
async def add_collection_files(
    collection_id: uuid.UUID, body: CollectionFilesUpdate, auth: CurrentUserDep, db: DbDep
) -> CollectionSummary:
    service = vault(auth, db)
    row = await service.get_collection(collection_id)
    await service.add_to_collection(row, body.file_ids)
    return _collection(row, await service.collection_count(row))


@router.delete(
    "/collections/{collection_id}/files/{file_id}", status_code=204,
    summary="Remove a file from a collection", responses=ERRORS,
)  # fmt: skip
async def remove_collection_file(
    collection_id: uuid.UUID, file_id: uuid.UUID, auth: CurrentUserDep, db: DbDep
) -> Response:
    service = vault(auth, db)
    await service.remove_from_collection(await service.get_collection(collection_id), file_id)
    return Response(status_code=204)
