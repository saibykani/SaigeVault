"""Vault file management on MongoDB (metadata) + object storage (content).

Every query filters by `user_id`. Content lives in R2 under
`{category}/{user_id}/{file_id}.{ext}`; folders, tags and collections exist
only in the database.
"""

from __future__ import annotations

import contextlib
import hashlib
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, BinaryIO

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from saige_api.core.errors import AppError, ConflictError, NotFoundError
from saige_api.db import Doc, new_id, now
from saige_api.enums import DataSource, DocumentType, ProcessingStatus
from saige_api.files.validation import FileKind, sanitize_filename
from saige_api.storage.base import ObjectStore, StorageNotFoundError

MAX_FOLDER_DEPTH = 32
UPLOAD_CHUNK = 1024 * 1024
ROOT_NAME = "My Vault"

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

CATEGORIES = ("documents", "images", "certificates", "resumes", "other")
_CATEGORY_TYPES = {
    "certificates": DocumentType.CERTIFICATE,
    "resumes": DocumentType.RESUME,
}


class StorageNotConnectedError(AppError):
    status_code = 503
    code = "storage_not_configured"


def normalize_tag(name: str) -> str:
    return " ".join(name.strip().lstrip("#").split()).lower()[:64]


def category_for(kind: FileKind, document_type: DocumentType) -> str:
    if document_type is DocumentType.CERTIFICATE:
        return "certificates"
    if document_type is DocumentType.RESUME:
        return "resumes"
    if kind.extension in TYPE_GROUPS["image"]:
        return "images"
    if kind.extension in {"zip", "json", "xml"}:
        return "other"
    return "documents"


def object_key(category: str, user_id: uuid.UUID, file_id: uuid.UUID, extension: str) -> str:
    return f"{category}/{user_id}/{file_id}.{extension}"


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


_SORT_FIELDS = {
    "name": "name_lower",
    "updated": "updated_at",
    "created": "created_at",
    "size": "size_bytes",
    "type": "extension",
}


class VaultService:
    def __init__(self, db: Any, user_id: uuid.UUID) -> None:
        self.db = db
        self.user_id = user_id

    def _mine(self, **extra: Any) -> dict[str, Any]:
        return {"user_id": self.user_id, **extra}

    # -- folders --------------------------------------------------------

    async def get_folder(self, folder_id: uuid.UUID) -> Doc:
        raw = await self.db.folders.find_one(self._mine(_id=folder_id, deleted_at=None))
        if raw is None:
            raise NotFoundError("Folder not found")
        return Doc(raw)

    async def breadcrumbs(self, folder: Doc | None) -> list[tuple[uuid.UUID | None, str]]:
        chain: list[tuple[uuid.UUID | None, str]] = []
        current = folder
        while current is not None and len(chain) < MAX_FOLDER_DEPTH:
            chain.append((current.id, current.name))
            current = await self.get_folder(current.parent_id) if current.parent_id else None
        chain.append((None, ROOT_NAME))
        return list(reversed(chain))

    async def list_subfolders(self, parent_id: uuid.UUID | None) -> list[Doc]:
        cursor = self.db.folders.find(self._mine(parent_id=parent_id, deleted_at=None)).sort(
            "name_lower", ASCENDING
        )
        return [Doc(r) async for r in cursor]

    async def create_folder(self, name: str, parent_id: uuid.UUID | None) -> Doc:
        parent = await self.get_folder(parent_id) if parent_id else None
        if parent and len(await self.breadcrumbs(parent)) > MAX_FOLDER_DEPTH:
            raise ConflictError("Folders can be nested at most 32 levels deep")
        clean = sanitize_filename(name)
        at = now()
        folder = {
            "_id": new_id(),
            "user_id": self.user_id,
            "parent_id": parent.id if parent else None,
            "name": clean,
            "name_lower": clean.lower(),
            "created_at": at,
            "updated_at": at,
            "deleted_at": None,
        }
        await self.db.folders.insert_one(folder)
        return Doc(folder)

    async def _is_descendant(self, candidate: Doc, ancestor_id: uuid.UUID) -> bool:
        current: Doc | None = candidate
        for _ in range(MAX_FOLDER_DEPTH + 1):
            if current is None:
                return False
            if current.id == ancestor_id:
                return True
            current = await self.get_folder(current.parent_id) if current.parent_id else None
        return True  # pathological depth: refuse

    async def update_folder(
        self, folder: Doc, *, name: str | None, parent_id: uuid.UUID | None, move_to_root: bool
    ) -> Doc:
        updates: dict[str, Any] = {}
        if name is not None:
            clean = sanitize_filename(name)
            updates.update(name=clean, name_lower=clean.lower())
        if move_to_root or parent_id is not None:
            target = await self.get_folder(parent_id) if parent_id else None
            if target is not None and await self._is_descendant(target, folder.id):
                raise ConflictError("A folder can't be moved into itself")
            updates["parent_id"] = target.id if target else None
        if updates:
            updates["updated_at"] = now()
            await self.db.folders.update_one(self._mine(_id=folder.id), {"$set": updates})
            folder.update(updates)
        return folder

    async def delete_folder(self, folder: Doc) -> None:
        has_files = await self.db.files.count_documents(
            self._mine(folder_id=folder.id, deleted_at=None), limit=1
        )
        has_folders = await self.db.folders.count_documents(
            self._mine(parent_id=folder.id, deleted_at=None), limit=1
        )
        if has_files or has_folders:
            raise ConflictError(
                "Only empty folders can be deleted. Move or delete its contents first."
            )
        await self.db.folders.update_one(self._mine(_id=folder.id), {"$set": {"deleted_at": now()}})

    # -- files: queries ---------------------------------------------------

    async def get_file(self, file_id: uuid.UUID, *, include_trashed: bool = False) -> Doc:
        query = self._mine(_id=file_id)
        if not include_trashed:
            query["deleted_at"] = None
        raw = await self.db.files.find_one(query)
        if raw is None:
            raise NotFoundError("File not found")
        return Doc(raw)

    async def _query(self, filters: FileFilters) -> dict[str, Any]:
        query = self._mine()
        query["deleted_at"] = {"$ne": None} if filters.trashed else None
        searching = any(
            [filters.query, filters.type_group, filters.document_type, filters.starred, filters.tag,
             filters.collection_id, filters.trashed, filters.all_folders]
        )  # fmt: skip
        if not searching or filters.folder_id is not None:
            query["folder_id"] = filters.folder_id
        if filters.query:
            query["name_lower"] = {"$regex": re.escape(filters.query.strip().lower())}
        if filters.type_group:
            query["extension"] = {"$in": list(TYPE_GROUPS.get(filters.type_group, ()))}
        if filters.document_type:
            query["document_type"] = filters.document_type.value
        if filters.starred is not None:
            query["is_starred"] = filters.starred
        if filters.tag:
            tag = await self.db.tags.find_one(self._mine(name_lower=normalize_tag(filters.tag)))
            query["tag_ids"] = tag["_id"] if tag else new_id()  # unknown tag: no matches
        if filters.collection_id:
            collection = await self.get_collection(filters.collection_id)
            query["_id"] = {"$in": collection.file_ids or []}
        return query

    async def list_files(self, filters: FileFilters) -> tuple[list[Doc], int]:
        query = await self._query(filters)
        total = await self.db.files.count_documents(query)
        field = _SORT_FIELDS.get(filters.sort, "updated_at")
        direction = DESCENDING if filters.descending else ASCENDING
        cursor = (
            self.db.files.find(query)
            .sort([(field, direction), ("_id", ASCENDING)])
            .skip(filters.offset)
            .limit(filters.limit)
        )
        return [Doc(r) async for r in cursor], int(total)

    async def tags_for(self, files: Sequence[Doc]) -> dict[uuid.UUID, list[Doc]]:
        ids = {t for f in files for t in (f.tag_ids or [])}
        if not ids:
            return {}
        tags = {
            r["_id"]: Doc(r) async for r in self.db.tags.find(self._mine(_id={"$in": list(ids)}))
        }
        return {
            f.id: sorted(
                (tags[t] for t in (f.tag_ids or []) if t in tags), key=lambda t: t.name_lower
            )
            for f in files
        }

    # -- files: upload & content ------------------------------------------------

    async def upload(
        self,
        objects: ObjectStore,
        *,
        stream: BinaryIO,
        size: int,
        filename: str,
        kind: FileKind,
        folder_id: uuid.UUID | None,
        category: str | None = None,
    ) -> Doc:
        folder = await self.get_folder(folder_id) if folder_id else None
        digest = hashlib.sha256()
        stream.seek(0)
        while chunk := stream.read(UPLOAD_CHUNK):
            digest.update(chunk)
        stream.seek(0)

        document_type = _CATEGORY_TYPES.get(category or "", kind.default_document_type)
        bucket = category if category in CATEGORIES else category_for(kind, document_type)
        file_id = new_id()
        key = object_key(bucket, self.user_id, file_id, kind.extension)
        await objects.put(key, stream, size=size, content_type=kind.mime_type)
        at = now()
        file: dict[str, Any] = {
            "_id": file_id,
            "user_id": self.user_id,
            "folder_id": folder.id if folder else None,
            "name": filename,
            "name_lower": filename.lower(),
            "extension": kind.extension,
            "mime_type": kind.mime_type,
            "size_bytes": size,
            "checksum": digest.hexdigest(),
            "category": bucket,
            "object_key": key,
            "document_type": document_type.value,
            "document_type_source": DataSource.SYSTEM.value
            if document_type is not DocumentType.UNCLASSIFIED
            else None,
            "is_starred": False,
            "processing_status": ProcessingStatus.PENDING.value,
            "tag_ids": [],
            "access_count": 0,
            "last_accessed_at": None,
            "created_at": at,
            "updated_at": at,
            "deleted_at": None,
        }
        try:
            await self.db.files.insert_one(file)
        except Exception:
            with contextlib.suppress(Exception):
                await objects.delete(key)  # don't leave orphaned content behind
            raise
        return Doc(file)

    async def record_access(self, file: Doc) -> None:
        await self.db.files.update_one(
            self._mine(_id=file.id),
            {"$set": {"last_accessed_at": now()}, "$inc": {"access_count": 1}},
        )

    # -- files: mutations ---------------------------------------------------

    async def _set(self, file: Doc, updates: dict[str, Any]) -> None:
        updates["updated_at"] = now()
        await self.db.files.update_one(self._mine(_id=file.id), {"$set": updates})
        file.update(updates)

    async def update_file(
        self,
        file: Doc,
        *,
        name: str | None = None,
        folder_id: uuid.UUID | None = None,
        move_to_root: bool = False,
        is_starred: bool | None = None,
        document_type: DocumentType | None = None,
    ) -> list[str]:
        """Returns the list of changed aspects (for auditing)."""
        changed: list[str] = []
        updates: dict[str, Any] = {}
        if name is not None:
            clean = sanitize_filename(name)
            # The extension identifies the validated content type: keep it.
            if file.extension and not clean.lower().endswith(f".{file.extension}"):
                clean = f"{clean}.{file.extension}"
            if clean != file.name:
                updates.update(name=clean, name_lower=clean.lower())
                changed.append("rename")
        if move_to_root or folder_id is not None:
            target = await self.get_folder(folder_id) if folder_id else None
            new_parent = target.id if target else None
            if new_parent != file.folder_id:
                updates["folder_id"] = new_parent
                changed.append("move")
        if is_starred is not None and is_starred != file.is_starred:
            updates["is_starred"] = is_starred
            changed.append("star")
        if document_type is not None:
            updates.update(
                document_type=document_type.value, document_type_source=DataSource.USER.value
            )
            changed.append("classify")
        if updates:
            await self._set(file, updates)
        return changed

    async def trash(self, file: Doc) -> None:
        await self._set(file, {"deleted_at": now()})

    async def restore(self, file: Doc) -> None:
        updates: dict[str, Any] = {"deleted_at": None}
        if file.folder_id:
            parent = await self.db.folders.find_one(self._mine(_id=file.folder_id))
            if parent is None or parent.get("deleted_at") is not None:
                updates["folder_id"] = None  # its folder is gone: restore to the root
        await self._set(file, updates)

    async def delete_permanently(self, objects: ObjectStore | None, file: Doc) -> None:
        if file.deleted_at is None:
            raise ConflictError("Move the file to trash before deleting it permanently")
        if objects is not None and file.object_key:
            with contextlib.suppress(StorageNotFoundError):
                await objects.delete(file.object_key)
        await self.db.files.delete_one(self._mine(_id=file.id))
        await self.db.collections.update_many(
            self._mine(file_ids=file.id), {"$pull": {"file_ids": file.id}}
        )

    # -- tags ---------------------------------------------------------------

    async def list_tags(self) -> list[Doc]:
        return [Doc(r) async for r in self.db.tags.find(self._mine()).sort("name_lower", 1)]

    async def set_file_tags(self, file: Doc, names: Sequence[str]) -> list[Doc]:
        wanted: dict[str, str] = {}
        for raw in names:
            normalized = normalize_tag(raw)
            if normalized:
                wanted.setdefault(normalized, raw.strip().lstrip("#")[:64])
        tags: list[Doc] = []
        for normalized, display in wanted.items():
            found = await self.db.tags.find_one(self._mine(name_lower=normalized))
            if found is None:
                found = {
                    "_id": new_id(),
                    "user_id": self.user_id,
                    "name": display,
                    "name_lower": normalized,
                    "color": None,
                    "created_at": now(),
                }
                try:
                    await self.db.tags.insert_one(found)
                except DuplicateKeyError:
                    found = await self.db.tags.find_one(self._mine(name_lower=normalized))
            assert found is not None  # noqa: S101
            tags.append(Doc(found))
        await self._set(file, {"tag_ids": [t.id for t in tags]})
        return tags

    async def delete_tag(self, tag_id: uuid.UUID) -> None:
        result = await self.db.tags.delete_one(self._mine(_id=tag_id))
        if not result.deleted_count:
            raise NotFoundError("Tag not found")
        await self.db.files.update_many(self._mine(tag_ids=tag_id), {"$pull": {"tag_ids": tag_id}})

    # -- collections ----------------------------------------------------------

    async def _live_count(self, file_ids: Sequence[uuid.UUID]) -> int:
        if not file_ids:
            return 0
        return int(
            await self.db.files.count_documents(
                self._mine(_id={"$in": list(file_ids)}, deleted_at=None)
            )
        )

    async def collection_count(self, collection: Doc) -> int:
        return await self._live_count(collection.file_ids or [])

    async def list_collections(self) -> list[tuple[Doc, int]]:
        rows = [
            Doc(r)
            async for r in self.db.collections.find(self._mine(deleted_at=None)).sort(
                [("sort_order", ASCENDING), ("name_lower", ASCENDING)]
            )
        ]
        return [(c, await self.collection_count(c)) for c in rows]

    async def get_collection(self, collection_id: uuid.UUID) -> Doc:
        raw = await self.db.collections.find_one(self._mine(_id=collection_id, deleted_at=None))
        if raw is None:
            raise NotFoundError("Collection not found")
        return Doc(raw)

    async def _name_taken(self, name: str, *, except_id: uuid.UUID | None = None) -> bool:
        query = self._mine(name_lower=name.strip().lower(), deleted_at=None)
        if except_id is not None:
            query["_id"] = {"$ne": except_id}
        return bool(await self.db.collections.count_documents(query, limit=1))

    async def create_collection(
        self, name: str, description: str | None, color: str | None, icon: str | None
    ) -> Doc:
        if await self._name_taken(name):
            raise ConflictError("A collection with that name already exists")
        at = now()
        row = {
            "_id": new_id(),
            "user_id": self.user_id,
            "name": name.strip(),
            "name_lower": name.strip().lower(),
            "description": description,
            "color": color,
            "icon": icon,
            "file_ids": [],
            "sort_order": 0,
            "created_at": at,
            "updated_at": at,
            "deleted_at": None,
        }
        await self.db.collections.insert_one(row)
        return Doc(row)

    async def update_collection(self, row: Doc, updates: dict[str, Any]) -> Doc:
        if "name" in updates:
            if await self._name_taken(updates["name"], except_id=row.id):
                raise ConflictError("A collection with that name already exists")
            updates["name_lower"] = updates["name"].lower()
        updates["updated_at"] = now()
        await self.db.collections.update_one(self._mine(_id=row.id), {"$set": updates})
        row.update(updates)
        return row

    async def delete_collection(self, row: Doc) -> None:
        await self.db.collections.update_one(
            self._mine(_id=row.id), {"$set": {"deleted_at": now()}}
        )

    async def add_to_collection(self, collection: Doc, file_ids: Sequence[uuid.UUID]) -> int:
        owned = [
            r["_id"]
            async for r in self.db.files.find(
                self._mine(_id={"$in": list(dict.fromkeys(file_ids))}, deleted_at=None),
                projection={"_id": 1},
            )
        ]
        present = set(collection.file_ids or [])
        new = [f for f in owned if f not in present]
        if new:
            await self.db.collections.update_one(
                self._mine(_id=collection.id),
                {"$push": {"file_ids": {"$each": new}}, "$set": {"updated_at": now()}},
            )
            collection["file_ids"] = [*(collection.file_ids or []), *new]
        return len(new)

    async def remove_from_collection(self, collection: Doc, file_id: uuid.UUID) -> None:
        result = await self.db.collections.update_one(
            self._mine(_id=collection.id, file_ids=file_id), {"$pull": {"file_ids": file_id}}
        )
        if not result.modified_count:
            raise NotFoundError("File is not in this collection")

    # -- stats ------------------------------------------------------------------

    async def stats(self) -> dict[str, object]:
        live = self._mine(deleted_at=None)
        files = self.db.files

        async def count(**extra: Any) -> int:
            return int(await files.count_documents({**live, **extra}))

        office = [*TYPE_GROUPS["document"], *TYPE_GROUPS["spreadsheet"],
                  *TYPE_GROUPS["presentation"], *TYPE_GROUPS["text"]]  # fmt: skip
        total_bytes = 0
        async for row in await files.aggregate(
            [{"$match": live}, {"$group": {"_id": None, "n": {"$sum": "$size_bytes"}}}]
        ):
            total_bytes = int(row["n"])
        by_type: dict[str, int] = {}
        async for row in await files.aggregate(
            [{"$match": live}, {"$group": {"_id": "$document_type", "n": {"$sum": 1}}}]
        ):
            by_type[str(row["_id"])] = int(row["n"])
        return {
            "total_files": await count(),
            "total_bytes": total_bytes,
            "pdfs": await count(extension="pdf"),
            "images": await count(extension={"$in": list(TYPE_GROUPS["image"])}),
            "documents": await count(extension={"$in": office}),
            "starred": await count(is_starred=True),
            "pending_processing": await count(
                processing_status={"$in": [s.value for s in UNPROCESSED]}
            ),
            "in_trash": int(await files.count_documents(self._mine(deleted_at={"$ne": None}))),
            "by_document_type": by_type,
        }
