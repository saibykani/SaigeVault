"""Vault file management on top of a storage provider.

Every query is scoped to the authenticated user. A file or folder that does
not exist and one that belongs to someone else are indistinguishable (404).
The storage provider holds content; PostgreSQL holds references and metadata.
"""

from __future__ import annotations

import contextlib
import hashlib
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, BinaryIO

from sqlalchemy import Select, and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from saige_api.core.errors import AppError, ConflictError, NotFoundError
from saige_api.files.validation import FileKind, sanitize_filename
from saige_api.models import (
    Collection,
    CollectionFile,
    File,
    FileTag,
    FileVersion,
    Folder,
    StorageConnection,
    Tag,
)
from saige_api.models.enums import (
    DataSource,
    DocumentType,
    FileVisibility,
    ProcessingStatus,
    StageStatus,
    StorageConnectionStatus,
    TagStatus,
)
from saige_api.storage.base import StorageNotFoundError, StorageProvider

MAX_FOLDER_DEPTH = 32
UPLOAD_CHUNK = 1024 * 1024

UNPROCESSED = (ProcessingStatus.PENDING, ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING)

TYPE_GROUPS: dict[str, tuple[str, ...]] = {
    "pdf": ("pdf",),
    "image": ("png", "jpg", "jpeg", "webp", "gif"),
    "document": ("doc", "docx"),
    "spreadsheet": ("xls", "xlsx", "csv"),
    "presentation": ("ppt", "pptx"),
    "text": ("txt", "md", "json", "xml"),
    "archive": ("zip",),
}


class StorageNotConnectedError(AppError):
    status_code = 409
    code = "storage_not_connected"


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def normalize_tag(name: str) -> str:
    return " ".join(name.strip().lstrip("#").split()).lower()[:64]


@dataclass(frozen=True, slots=True)
class FileFilters:
    folder_id: uuid.UUID | None = None
    all_folders: bool = False
    query: str | None = None
    type_group: str | None = None
    document_type: DocumentType | None = None
    starred: bool | None = None
    trashed: bool = False
    tag: str | None = None
    collection_id: uuid.UUID | None = None
    sort: str = "updated"
    descending: bool = True
    limit: int = 100
    offset: int = 0


class VaultService:
    def __init__(self, db: AsyncSession, user_id: uuid.UUID) -> None:
        self.db = db
        self.user_id = user_id

    # -- storage --------------------------------------------------------

    async def active_connection(self) -> StorageConnection:
        row = await self.db.scalar(
            select(StorageConnection)
            .where(
                StorageConnection.user_id == self.user_id,
                StorageConnection.status == StorageConnectionStatus.ACTIVE,
            )
            .order_by(StorageConnection.connected_at.desc())
            .limit(1)
        )
        if row is None:
            raise StorageNotConnectedError("Connect Google Drive in Settings to store files.")
        return row

    async def root_folder_id(self, connection: StorageConnection, provider: StorageProvider) -> str:
        if not connection.root_folder_id:
            root = await provider.ensure_root_folder("Saige Vault")
            connection.root_folder_id = root.id
            await self.db.flush()
        assert connection.root_folder_id is not None  # noqa: S101
        return connection.root_folder_id

    # -- folders --------------------------------------------------------

    async def get_folder(self, folder_id: uuid.UUID) -> Folder:
        folder = await self.db.scalar(
            select(Folder).where(
                Folder.id == folder_id, Folder.user_id == self.user_id, Folder.deleted_at.is_(None)
            )
        )
        if folder is None:
            raise NotFoundError("Folder not found")
        return folder

    async def breadcrumbs(self, folder: Folder | None) -> list[tuple[uuid.UUID | None, str]]:
        chain: list[tuple[uuid.UUID | None, str]] = []
        current = folder
        while current is not None and len(chain) < MAX_FOLDER_DEPTH:
            chain.append((current.id, current.name))
            current = (
                await self.get_folder(current.parent_folder_id)
                if current.parent_folder_id
                else None
            )
        chain.append((None, "My Vault"))
        return list(reversed(chain))

    async def list_subfolders(self, parent_id: uuid.UUID | None) -> Sequence[Folder]:
        rows = await self.db.scalars(
            select(Folder)
            .where(
                Folder.user_id == self.user_id,
                Folder.deleted_at.is_(None),
                Folder.parent_folder_id.is_(None)
                if parent_id is None
                else Folder.parent_folder_id == parent_id,
            )
            .order_by(func.lower(Folder.name))
        )
        return rows.all()

    async def _storage_parent(
        self, provider: StorageProvider, connection: StorageConnection, folder: Folder | None
    ) -> str:
        return (
            folder.storage_folder_id if folder else await self.root_folder_id(connection, provider)
        )

    async def create_folder(
        self,
        provider: StorageProvider,
        connection: StorageConnection,
        name: str,
        parent_id: uuid.UUID | None,
    ) -> Folder:
        parent = await self.get_folder(parent_id) if parent_id else None
        if parent and len(await self.breadcrumbs(parent)) > MAX_FOLDER_DEPTH:
            raise ConflictError("Folders can be nested at most 32 levels deep")
        clean = sanitize_filename(name)
        item = await provider.create_folder(
            clean, await self._storage_parent(provider, connection, parent)
        )
        folder = Folder(
            user_id=self.user_id,
            storage_connection_id=connection.id,
            storage_folder_id=item.id,
            parent_folder_id=parent.id if parent else None,
            name=clean,
        )
        self.db.add(folder)
        await self.db.flush()
        return folder

    async def _is_descendant(self, candidate: Folder, ancestor_id: uuid.UUID) -> bool:
        current: Folder | None = candidate
        for _ in range(MAX_FOLDER_DEPTH + 1):
            if current is None:
                return False
            if current.id == ancestor_id:
                return True
            current = (
                await self.get_folder(current.parent_folder_id)
                if current.parent_folder_id
                else None
            )
        return True  # pathological depth: refuse

    async def update_folder(
        self,
        provider: StorageProvider,
        connection: StorageConnection,
        folder: Folder,
        *,
        name: str | None,
        parent_id: uuid.UUID | None,
        move_to_root: bool,
    ) -> Folder:
        if name is not None:
            clean = sanitize_filename(name)
            await provider.rename(folder.storage_folder_id, clean)
            folder.name = clean
        if move_to_root or parent_id is not None:
            target = await self.get_folder(parent_id) if parent_id else None
            if target is not None and await self._is_descendant(target, folder.id):
                raise ConflictError("A folder can't be moved into itself")
            await provider.move(
                folder.storage_folder_id, await self._storage_parent(provider, connection, target)
            )
            folder.parent_folder_id = target.id if target else None
        await self.db.flush()
        return folder

    async def delete_folder(self, provider: StorageProvider, folder: Folder) -> None:
        has_files = await self.db.scalar(
            select(func.count())
            .select_from(File)
            .where(
                File.user_id == self.user_id,
                File.parent_folder_id == folder.id,
                File.deleted_at.is_(None),
            )
        )
        has_folders = await self.db.scalar(
            select(func.count())
            .select_from(Folder)
            .where(
                Folder.user_id == self.user_id,
                Folder.parent_folder_id == folder.id,
                Folder.deleted_at.is_(None),
            )
        )
        if has_files or has_folders:
            raise ConflictError(
                "Only empty folders can be deleted. Move or delete its contents first."
            )
        await provider.trash(folder.storage_folder_id)
        folder.deleted_at = datetime.now(UTC)
        await self.db.flush()

    # -- files: queries ---------------------------------------------------

    async def get_file(self, file_id: uuid.UUID, *, include_trashed: bool = False) -> File:
        conditions = [File.id == file_id, File.user_id == self.user_id]
        if not include_trashed:
            conditions.append(File.deleted_at.is_(None))
        row = await self.db.scalar(select(File).where(*conditions))
        if row is None:
            raise NotFoundError("File not found")
        return row

    def _filtered(self, filters: FileFilters) -> Select[File]:
        stmt = select(File).where(File.user_id == self.user_id)
        stmt = stmt.where(
            File.deleted_at.is_not(None) if filters.trashed else File.deleted_at.is_(None)
        )
        searching = any(
            [filters.query, filters.type_group, filters.document_type, filters.starred, filters.tag,
             filters.collection_id, filters.trashed, filters.all_folders]
        )  # fmt: skip
        if not searching:
            stmt = stmt.where(
                File.parent_folder_id.is_(None)
                if filters.folder_id is None
                else File.parent_folder_id == filters.folder_id
            )
        elif filters.folder_id is not None:
            stmt = stmt.where(File.parent_folder_id == filters.folder_id)
        if filters.query:
            stmt = stmt.where(
                File.name.ilike(f"%{escape_like(filters.query.strip())}%", escape="\\")
            )
        if filters.type_group:
            stmt = stmt.where(File.extension.in_(TYPE_GROUPS.get(filters.type_group, ())))
        if filters.document_type:
            stmt = stmt.where(File.document_type == filters.document_type)
        if filters.starred is not None:
            stmt = stmt.where(File.is_starred.is_(filters.starred))
        if filters.tag:
            stmt = stmt.where(
                File.id.in_(
                    select(FileTag.file_id)
                    .join(Tag, and_(Tag.id == FileTag.tag_id, Tag.user_id == FileTag.user_id))
                    .where(
                        FileTag.user_id == self.user_id,
                        Tag.normalized_name == normalize_tag(filters.tag),
                        FileTag.status == TagStatus.CONFIRMED,
                    )
                )
            )
        if filters.collection_id:
            stmt = stmt.where(
                File.id.in_(
                    select(CollectionFile.file_id).where(
                        CollectionFile.user_id == self.user_id,
                        CollectionFile.collection_id == filters.collection_id,
                    )
                )
            )
        return stmt

    async def list_files(self, filters: FileFilters) -> tuple[Sequence[File], int]:
        base = self._filtered(filters)
        total = await self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        columns: dict[str, Any] = {
            "name": File.name,
            "updated": File.updated_at,
            "created": File.created_at,
            "size": File.size_bytes,
            "type": File.extension,
        }
        column = columns.get(filters.sort, File.updated_at)
        key = func.lower(File.name) if filters.sort == "name" else column
        order = key.desc() if filters.descending else key.asc()
        rows = await self.db.scalars(
            base.order_by(order, File.id).limit(filters.limit).offset(filters.offset)
        )
        return rows.all(), int(total)

    async def tags_for(self, file_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[Tag]]:
        if not file_ids:
            return {}
        rows = await self.db.execute(
            select(FileTag.file_id, Tag)
            .join(Tag, and_(Tag.id == FileTag.tag_id, Tag.user_id == FileTag.user_id))
            .where(
                FileTag.user_id == self.user_id,
                FileTag.file_id.in_(file_ids),
                FileTag.status == TagStatus.CONFIRMED,
            )
            .order_by(Tag.normalized_name)
        )
        result: dict[uuid.UUID, list[Tag]] = {}
        for file_id, tag in rows.all():
            result.setdefault(file_id, []).append(tag)
        return result

    # -- files: upload & content -------------------------------------------

    async def upload(
        self,
        provider: StorageProvider,
        connection: StorageConnection,
        *,
        stream: BinaryIO,
        size: int,
        filename: str,
        kind: FileKind,
        folder_id: uuid.UUID | None,
    ) -> File:
        folder = await self.get_folder(folder_id) if folder_id else None
        parent = await self._storage_parent(provider, connection, folder)

        digest = hashlib.sha256()
        stream.seek(0)
        while chunk := stream.read(UPLOAD_CHUNK):
            digest.update(chunk)
        stream.seek(0)

        async def content() -> AsyncIterator[bytes]:
            while chunk := stream.read(UPLOAD_CHUNK):
                yield chunk

        item = await provider.upload(
            name=filename, parent_id=parent, mime_type=kind.mime_type, size=size, content=content()
        )
        file = File(
            user_id=self.user_id,
            storage_provider=connection.provider,
            storage_connection_id=connection.id,
            storage_file_id=item.id,
            parent_folder_id=folder.id if folder else None,
            name=filename,
            extension=kind.extension,
            mime_type=kind.mime_type,
            size_bytes=size,
            checksum=digest.hexdigest(),
            storage_modified_at=item.modified_at,
            visibility=FileVisibility.PRIVATE,
            document_type=kind.default_document_type,
            document_type_source=DataSource.SYSTEM
            if kind.default_document_type is not DocumentType.UNCLASSIFIED
            else None,
            processing_status=ProcessingStatus.PENDING,
            ocr_status=StageStatus.PENDING,
            extraction_status=StageStatus.PENDING,
            embedding_status=StageStatus.PENDING,
        )
        self.db.add(file)
        await self.db.flush()
        self.db.add(
            FileVersion(
                user_id=self.user_id,
                file_id=file.id,
                version_number=1,
                storage_revision_id=item.revision_id or item.id,
                size_bytes=size,
                checksum=file.checksum,
                mime_type=kind.mime_type,
                storage_modified_at=item.modified_at,
            )
        )
        await self.db.flush()
        return file

    async def record_access(self, file: File) -> None:
        file.last_accessed_at = datetime.now(UTC)
        file.access_count = (file.access_count or 0) + 1
        await self.db.flush()

    # -- files: mutations ---------------------------------------------------

    async def update_file(
        self,
        provider: StorageProvider | None,
        connection: StorageConnection | None,
        file: File,
        *,
        name: str | None = None,
        folder_id: uuid.UUID | None = None,
        move_to_root: bool = False,
        is_starred: bool | None = None,
        document_type: DocumentType | None = None,
    ) -> list[str]:
        """Returns the list of changed aspects (for auditing)."""
        changed: list[str] = []
        if name is not None:
            clean = sanitize_filename(name)
            # The extension identifies the validated content type: keep it.
            if file.extension and not clean.lower().endswith(f".{file.extension}"):
                clean = f"{clean}.{file.extension}"
            if clean != file.name:
                assert provider is not None  # noqa: S101 - callers pass a provider for renames
                await provider.rename(file.storage_file_id, clean)
                file.name = clean
                changed.append("rename")
        if move_to_root or folder_id is not None:
            target = await self.get_folder(folder_id) if folder_id else None
            new_parent = target.id if target else None
            if new_parent != file.parent_folder_id:
                assert provider is not None and connection is not None  # noqa: S101
                await provider.move(
                    file.storage_file_id, await self._storage_parent(provider, connection, target)
                )
                file.parent_folder_id = new_parent
                changed.append("move")
        if is_starred is not None and is_starred != file.is_starred:
            file.is_starred = is_starred
            changed.append("star")
        if document_type is not None:
            file.document_type = document_type
            file.document_type_source = DataSource.USER
            file.document_type_confidence = None
            changed.append("classify")
        await self.db.flush()
        return changed

    async def trash(self, provider: StorageProvider, file: File) -> None:
        # Already gone from storage? Still hide it in the vault.
        with contextlib.suppress(StorageNotFoundError):
            await provider.trash(file.storage_file_id)
        file.deleted_at = datetime.now(UTC)
        await self.db.flush()

    async def restore(self, provider: StorageProvider, file: File) -> None:
        await provider.restore(file.storage_file_id)
        if file.parent_folder_id:
            parent = await self.db.scalar(
                select(Folder).where(
                    Folder.id == file.parent_folder_id, Folder.user_id == self.user_id
                )
            )
            if parent is None or parent.deleted_at is not None:
                file.parent_folder_id = None  # its folder is gone: restore to the root
        file.deleted_at = None
        await self.db.flush()

    async def delete_permanently(self, provider: StorageProvider, file: File) -> None:
        if file.deleted_at is None:
            raise ConflictError("Move the file to trash before deleting it permanently")
        with contextlib.suppress(StorageNotFoundError):
            await provider.delete_permanently(file.storage_file_id)
        await self.db.delete(file)
        await self.db.flush()

    # -- tags ---------------------------------------------------------------

    async def list_tags(self) -> Sequence[Tag]:
        rows = await self.db.scalars(
            select(Tag).where(Tag.user_id == self.user_id).order_by(Tag.normalized_name)
        )
        return rows.all()

    async def set_file_tags(self, file: File, names: Sequence[str]) -> list[Tag]:
        wanted: dict[str, str] = {}
        for raw in names:
            normalized = normalize_tag(raw)
            if normalized:
                wanted.setdefault(normalized, raw.strip().lstrip("#")[:64])
        existing = {
            t.normalized_name: t
            for t in (
                await self.db.scalars(
                    select(Tag).where(Tag.user_id == self.user_id, Tag.normalized_name.in_(wanted))
                )
            ).all()
        }
        tags: list[Tag] = []
        for normalized, display in wanted.items():
            tag = existing.get(normalized)
            if tag is None:
                tag = Tag(
                    user_id=self.user_id,
                    name=display,
                    normalized_name=normalized,
                    is_sensitive=False,
                )
                self.db.add(tag)
                await self.db.flush()
            tags.append(tag)
        conditions = [
            FileTag.user_id == self.user_id,
            FileTag.file_id == file.id,
            FileTag.source == DataSource.USER,
        ]
        if tags:
            conditions.append(FileTag.tag_id.not_in([t.id for t in tags]))
        await self.db.execute(delete(FileTag).where(*conditions))
        current = set(
            (
                await self.db.scalars(
                    select(FileTag.tag_id).where(
                        FileTag.user_id == self.user_id, FileTag.file_id == file.id
                    )
                )
            ).all()
        )
        for tag in tags:
            if tag.id not in current:
                self.db.add(
                    FileTag(
                        user_id=self.user_id, file_id=file.id, tag_id=tag.id,
                        source=DataSource.USER, status=TagStatus.CONFIRMED,
                    )
                )  # fmt: skip
        await self.db.flush()
        return tags

    async def delete_tag(self, tag_id: uuid.UUID) -> None:
        tag = await self.db.scalar(select(Tag).where(Tag.id == tag_id, Tag.user_id == self.user_id))
        if tag is None:
            raise NotFoundError("Tag not found")
        await self.db.delete(tag)
        await self.db.flush()

    # -- collections ----------------------------------------------------------

    async def list_collections(self) -> list[tuple[Collection, int]]:
        counts = (
            select(CollectionFile.collection_id, func.count().label("n"))
            .join(
                File,
                and_(File.id == CollectionFile.file_id, File.user_id == CollectionFile.user_id),
            )
            .where(CollectionFile.user_id == self.user_id, File.deleted_at.is_(None))
            .group_by(CollectionFile.collection_id)
            .subquery()
        )
        rows = await self.db.execute(
            select(Collection, func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.collection_id == Collection.id)
            .where(Collection.user_id == self.user_id, Collection.deleted_at.is_(None))
            .order_by(Collection.sort_order, func.lower(Collection.name))
        )
        return [(c, int(n)) for c, n in rows.all()]

    async def get_collection(self, collection_id: uuid.UUID) -> Collection:
        row = await self.db.scalar(
            select(Collection).where(
                Collection.id == collection_id,
                Collection.user_id == self.user_id,
                Collection.deleted_at.is_(None),
            )
        )
        if row is None:
            raise NotFoundError("Collection not found")
        return row

    async def create_collection(
        self, name: str, description: str | None, color: str | None, icon: str | None
    ) -> Collection:
        clash = await self.db.scalar(
            select(Collection.id).where(
                Collection.user_id == self.user_id,
                Collection.deleted_at.is_(None),
                Collection.parent_collection_id.is_(None),
                func.lower(Collection.name) == name.strip().lower(),
            )
        )
        if clash:
            raise ConflictError("A collection with that name already exists")
        row = Collection(
            user_id=self.user_id, name=name.strip(), description=description, color=color, icon=icon
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def add_to_collection(self, collection: Collection, file_ids: Sequence[uuid.UUID]) -> int:
        owned = (
            await self.db.scalars(
                select(File.id).where(
                    File.user_id == self.user_id, File.id.in_(file_ids), File.deleted_at.is_(None)
                )
            )
        ).all()
        present = set(
            (
                await self.db.scalars(
                    select(CollectionFile.file_id).where(
                        CollectionFile.user_id == self.user_id,
                        CollectionFile.collection_id == collection.id,
                    )
                )
            ).all()
        )
        added = 0
        for file_id in owned:
            if file_id not in present:
                self.db.add(
                    CollectionFile(
                        user_id=self.user_id, collection_id=collection.id, file_id=file_id
                    )
                )
                added += 1
        await self.db.flush()
        return added

    async def remove_from_collection(self, collection: Collection, file_id: uuid.UUID) -> None:
        result = await self.db.execute(
            delete(CollectionFile).where(
                CollectionFile.user_id == self.user_id,
                CollectionFile.collection_id == collection.id,
                CollectionFile.file_id == file_id,
            )
        )
        if not getattr(result, "rowcount", 0):
            raise NotFoundError("File is not in this collection")
        await self.db.flush()

    # -- stats ------------------------------------------------------------------

    async def stats(self) -> dict[str, object]:
        live = and_(File.user_id == self.user_id, File.deleted_at.is_(None))
        row = (
            await self.db.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(File.size_bytes), 0),
                    func.count().filter(File.extension == "pdf"),
                    func.count().filter(File.extension.in_(TYPE_GROUPS["image"])),
                    func.count().filter(
                        or_(
                            File.extension.in_(TYPE_GROUPS["document"]),
                            File.extension.in_(TYPE_GROUPS["spreadsheet"]),
                            File.extension.in_(TYPE_GROUPS["presentation"]),
                            File.extension.in_(TYPE_GROUPS["text"]),
                        )
                    ),
                    func.count().filter(File.is_starred.is_(True)),
                    func.count().filter(
                        File.processing_status.in_(
                            [
                                ProcessingStatus.PENDING,
                                ProcessingStatus.QUEUED,
                                ProcessingStatus.PROCESSING,
                            ]
                        )
                    ),
                ).where(live)
            )
        ).one()
        in_trash = await self.db.scalar(
            select(func.count()).where(File.user_id == self.user_id, File.deleted_at.is_not(None))
        )
        by_type = await self.db.execute(
            select(File.document_type, func.count()).where(live).group_by(File.document_type)
        )
        return {
            "total_files": int(row[0]),
            "total_bytes": int(row[1]),
            "pdfs": int(row[2]),
            "images": int(row[3]),
            "documents": int(row[4]),
            "starred": int(row[5]),
            "pending_processing": int(row[6]),
            "in_trash": int(in_trash or 0),
            "by_document_type": {str(t.value): int(n) for t, n in by_type.all()},
        }
