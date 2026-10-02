"""File, folder, tag and collection API models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from saige_api.models.enums import DataSource, DocumentType, ProcessingStatus

SortKey = Literal["name", "updated", "created", "size", "type"]
TypeGroup = Literal["pdf", "image", "document", "spreadsheet", "presentation", "text", "archive"]
BulkAction = Literal["trash", "restore", "star", "unstar", "move"]


class TagRef(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None = None


class FileSummary(BaseModel):
    id: uuid.UUID
    name: str
    extension: str | None
    mime_type: str
    size_bytes: int
    folder_id: uuid.UUID | None
    document_type: DocumentType
    document_type_source: DataSource | None
    is_starred: bool
    processing_status: ProcessingStatus
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    last_accessed_at: datetime | None
    tags: list[TagRef] = []


class FolderSummary(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class Breadcrumb(BaseModel):
    id: uuid.UUID | None  # None = vault root
    name: str


class FileListResponse(BaseModel):
    folders: list[FolderSummary]
    files: list[FileSummary]
    total: int
    breadcrumbs: list[Breadcrumb]


class FileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    folder_id: uuid.UUID | None = Field(
        default=None, description="Target folder. Use move_to_root to move to the vault root."
    )
    move_to_root: bool = False
    is_starred: bool | None = None
    document_type: DocumentType | None = Field(
        default=None, description="User override of the document classification"
    )


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None
    move_to_root: bool = False


class BulkRequest(BaseModel):
    file_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    action: BulkAction
    folder_id: uuid.UUID | None = None


class BulkResult(BaseModel):
    succeeded: list[uuid.UUID]
    failed: list[uuid.UUID]


class TagListResponse(BaseModel):
    tags: list[TagRef]


class TagsUpdate(BaseModel):
    names: list[str] = Field(max_length=50)


class CollectionSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    color: str | None
    icon: str | None
    file_count: int
    created_at: datetime
    updated_at: datetime


class CollectionListResponse(BaseModel):
    collections: list[CollectionSummary]


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(default=None, max_length=64)


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class CollectionFilesUpdate(BaseModel):
    file_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class CollectionDetail(BaseModel):
    collection: CollectionSummary
    files: list[FileSummary]


class FileStats(BaseModel):
    total_files: int
    total_bytes: int
    pdfs: int
    images: int
    documents: int
    starred: int
    in_trash: int
    pending_processing: int
    by_document_type: dict[str, int]
