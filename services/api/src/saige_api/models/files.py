"""Files, versions, folders, metadata, tags and collections.

The storage provider is the source of truth for file content. These tables
hold references (provider file IDs) and application metadata only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from saige_api.db.base import (
    Base,
    CreatedAtMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UserOwnedMixin,
    UUIDPrimaryKeyMixin,
    owned_fk,
    str_enum,
    tenant_key,
)
from saige_api.models.enums import (
    DataSource,
    DocumentType,
    FileVisibility,
    ProcessingStatus,
    StageStatus,
    StorageProviderKind,
    TagStatus,
)


class Folder(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "folders"
    __table_args__ = (
        tenant_key("folders"),
        owned_fk("storage_connection_id", "storage_connections"),
        owned_fk("parent_folder_id", "folders"),
        UniqueConstraint("storage_connection_id", "storage_folder_id"),
        Index("ix_folders_user_parent", "user_id", "parent_folder_id"),
        CheckConstraint(
            "parent_folder_id IS NULL OR parent_folder_id <> id", name="not_own_parent"
        ),
    )

    storage_connection_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    storage_folder_id: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_folder_id: Mapped[uuid.UUID | None] = mapped_column()
    name: Mapped[str] = mapped_column(String(1024), nullable=False)


class File(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "files"
    __table_args__ = (
        tenant_key("files"),
        owned_fk("storage_connection_id", "storage_connections"),
        owned_fk("parent_folder_id", "folders", ondelete="SET NULL"),
        UniqueConstraint("storage_connection_id", "storage_file_id"),
        Index("ix_files_user_folder", "user_id", "parent_folder_id"),
        Index("ix_files_user_updated", "user_id", "updated_at"),
        Index("ix_files_user_document_type", "user_id", "document_type"),
        Index("ix_files_user_processing", "user_id", "processing_status"),
        Index(
            "ix_files_user_starred",
            "user_id",
            postgresql_where=text("is_starred AND deleted_at IS NULL"),
        ),
        Index("ix_files_checksum", "user_id", "checksum"),
        CheckConstraint("size_bytes >= 0", name="size_non_negative"),
        CheckConstraint(
            "document_type_confidence IS NULL OR "
            "(document_type_confidence >= 0 AND document_type_confidence <= 1)",
            name="confidence_range",
        ),
    )

    storage_provider: Mapped[StorageProviderKind] = mapped_column(
        str_enum(StorageProviderKind, "file_storage_provider"), nullable=False
    )
    storage_connection_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    storage_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_folder_id: Mapped[uuid.UUID | None] = mapped_column()

    name: Mapped[str] = mapped_column(String(1024), nullable=False)
    extension: Mapped[str | None] = mapped_column(String(32))
    # MIME type as detected server-side from content, never the client's claim.
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64))  # SHA-256 hex
    storage_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    visibility: Mapped[FileVisibility] = mapped_column(
        str_enum(FileVisibility, "file_visibility"),
        nullable=False,
        default=FileVisibility.PRIVATE,
    )
    is_starred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    document_type: Mapped[DocumentType] = mapped_column(
        str_enum(DocumentType, "document_type"),
        nullable=False,
        default=DocumentType.UNCLASSIFIED,
    )
    document_type_source: Mapped[DataSource | None] = mapped_column(
        str_enum(DataSource, "document_type_source")
    )
    document_type_confidence: Mapped[float | None] = mapped_column(Float)

    processing_status: Mapped[ProcessingStatus] = mapped_column(
        str_enum(ProcessingStatus, "processing_status"),
        nullable=False,
        default=ProcessingStatus.PENDING,
    )
    ocr_status: Mapped[StageStatus] = mapped_column(
        str_enum(StageStatus, "ocr_status"), nullable=False, default=StageStatus.PENDING
    )
    extraction_status: Mapped[StageStatus] = mapped_column(
        str_enum(StageStatus, "extraction_status"), nullable=False, default=StageStatus.PENDING
    )
    embedding_status: Mapped[StageStatus] = mapped_column(
        str_enum(StageStatus, "embedding_status"), nullable=False, default=StageStatus.PENDING
    )
    is_ai_indexed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    thumbnail_storage_key: Mapped[str | None] = mapped_column(String(512))


class FileVersion(UUIDPrimaryKeyMixin, UserOwnedMixin, CreatedAtMixin, Base):
    __tablename__ = "file_versions"
    __table_args__ = (
        tenant_key("file_versions"),
        owned_fk("file_id", "files"),
        UniqueConstraint("file_id", "version_number"),
        UniqueConstraint("file_id", "storage_revision_id"),
    )

    file_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_revision_id: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64))  # SHA-256 hex
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FileMetadata(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, Base):
    """Key/value structured data about a file (e.g. payslip net salary).

    `source` and `is_confirmed` make provenance explicit: AI-extracted values
    are suggestions until the user confirms them. `source_page` keeps every
    value traceable back to the original document.
    """

    __tablename__ = "file_metadata"
    __table_args__ = (
        owned_fk("file_id", "files"),
        UniqueConstraint("file_id", "key", "source"),
        Index("ix_file_metadata_user_key", "user_id", "key"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="confidence_range"
        ),
    )

    file_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    source: Mapped[DataSource] = mapped_column(
        str_enum(DataSource, "file_metadata_source"), nullable=False
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    source_page: Mapped[int | None] = mapped_column(Integer)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Tag(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (tenant_key("tags"), UniqueConstraint("user_id", "normalized_name"))

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str | None] = mapped_column(String(16))
    is_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FileTag(UserOwnedMixin, CreatedAtMixin, Base):
    __tablename__ = "file_tags"
    __table_args__ = (
        PrimaryKeyConstraint("file_id", "tag_id"),
        owned_fk("file_id", "files"),
        owned_fk("tag_id", "tags"),
        Index("ix_file_tags_tag", "tag_id"),
    )

    file_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    tag_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    source: Mapped[DataSource] = mapped_column(
        str_enum(DataSource, "file_tag_source"), nullable=False
    )
    status: Mapped[TagStatus] = mapped_column(
        str_enum(TagStatus, "file_tag_status"), nullable=False, default=TagStatus.CONFIRMED
    )
    confidence: Mapped[float | None] = mapped_column(Float)


class Collection(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Virtual grouping. A file may belong to many collections without copies."""

    __tablename__ = "collections"
    __table_args__ = (
        tenant_key("collections"),
        owned_fk("parent_collection_id", "collections"),
        Index(
            "uq_collections_user_parent_name",
            "user_id",
            func.coalesce(
                text("parent_collection_id"), text("'00000000-0000-0000-0000-000000000000'::uuid")
            ),
            func.lower(text("name")),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    parent_collection_id: Mapped[uuid.UUID | None] = mapped_column()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(64))
    color: Mapped[str | None] = mapped_column(String(16))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CollectionFile(UserOwnedMixin, CreatedAtMixin, Base):
    __tablename__ = "collection_files"
    __table_args__ = (
        PrimaryKeyConstraint("collection_id", "file_id"),
        owned_fk("collection_id", "collections"),
        owned_fk("file_id", "files"),
        Index("ix_collection_files_file", "file_id"),
    )

    collection_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    file_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
