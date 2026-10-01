"""Document processing: jobs, extracted content, entities, summaries, chunks.

Traceability chain (never broken):
    answer -> document_chunks -> page -> files -> storage provider file
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from saige_api.db.base import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UserOwnedMixin,
    UUIDPrimaryKeyMixin,
    owned_fk,
    str_enum,
    tenant_key,
)
from saige_api.models.enums import (
    ChunkingStrategy,
    DataSource,
    EmbeddingStatus,
    ExtractionMethod,
    JobStatus,
    JobType,
    SummaryType,
)


class DocumentProcessingJob(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, Base):
    """Durable record of a background job. Redis holds the queue; this table
    holds the truth about status, attempts, progress and failures."""

    __tablename__ = "document_processing_jobs"
    __table_args__ = (
        tenant_key("document_processing_jobs"),
        owned_fk("file_id", "files"),
        Index("ix_jobs_status_scheduled", "status", "next_attempt_at"),
        Index("ix_jobs_user_file", "user_id", "file_id"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="progress_range"),
        CheckConstraint("attempt >= 0 AND attempt <= max_attempts", name="attempt_bounds"),
    )

    file_id: Mapped[uuid.UUID | None] = mapped_column()
    job_type: Mapped[JobType] = mapped_column(str_enum(JobType, "job_type"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        str_enum(JobStatus, "job_status"), nullable=False, default=JobStatus.QUEUED
    )
    # Deterministic key (e.g. "document_processing:<file_id>:<version>") so a
    # re-enqueue of the same work is a no-op instead of duplicate processing.
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    attempt: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=5)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    current_stage: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    # Sanitised error information only — never document content.
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentExtractedContent(UUIDPrimaryKeyMixin, UserOwnedMixin, CreatedAtMixin, Base):
    """Text per page, from native extraction or OCR."""

    __tablename__ = "document_extracted_content"
    __table_args__ = (
        owned_fk("file_id", "files"),
        owned_fk("file_version_id", "file_versions", ondelete="SET NULL"),
        UniqueConstraint(
            "file_id", "file_version_id", "page_number", "method", name="uq_extracted_content_page"
        ),
        CheckConstraint("page_number >= 1", name="page_positive"),
    )

    file_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    file_version_id: Mapped[uuid.UUID | None] = mapped_column()
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[ExtractionMethod] = mapped_column(
        str_enum(ExtractionMethod, "extraction_method"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16))
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    # [{"text": str, "bbox": [x0, y0, x1, y1], "confidence": float}, ...]
    bounding_boxes: Mapped[list[Any] | None] = mapped_column()


class DocumentEntity(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, Base):
    """Entity mentioned in a document (company, skill, date, amount...).

    Also the seed of the future personal knowledge graph: relationships can be
    added in a dedicated table keyed on these rows without schema upheaval.
    """

    __tablename__ = "document_entities"
    __table_args__ = (
        tenant_key("document_entities"),
        owned_fk("file_id", "files"),
        Index("ix_document_entities_lookup", "user_id", "entity_type", "normalized_value"),
    )

    file_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    source: Mapped[DataSource] = mapped_column(
        str_enum(DataSource, "document_entity_source"), nullable=False
    )
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)


class DocumentSummary(UUIDPrimaryKeyMixin, UserOwnedMixin, CreatedAtMixin, Base):
    __tablename__ = "document_summaries"
    __table_args__ = (
        owned_fk("file_id", "files"),
        owned_fk("file_version_id", "file_versions", ondelete="SET NULL"),
        Index("ix_document_summaries_file_type", "file_id", "summary_type"),
    )

    file_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    file_version_id: Mapped[uuid.UUID | None] = mapped_column()
    summary_type: Mapped[SummaryType] = mapped_column(
        str_enum(SummaryType, "summary_type"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_chunk_ids: Mapped[list[Any]] = mapped_column(nullable=False, default=list)
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)


class DocumentChunk(UUIDPrimaryKeyMixin, UserOwnedMixin, CreatedAtMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        tenant_key("document_chunks"),
        owned_fk("file_id", "files"),
        owned_fk("file_version_id", "file_versions", ondelete="SET NULL"),
        UniqueConstraint("file_id", "file_version_id", "strategy", "chunk_index"),
        Index("ix_document_chunks_user_file", "user_id", "file_id"),
        # Full-text index for keyword/hybrid retrieval.
        Index(
            "ix_document_chunks_fts",
            text("to_tsvector('simple', content)"),
            postgresql_using="gin",
        ),
        CheckConstraint("page_start IS NULL OR page_start >= 1", name="page_start_positive"),
        CheckConstraint(
            "page_end IS NULL OR page_start IS NULL OR page_end >= page_start", name="page_order"
        ),
    )

    file_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    file_version_id: Mapped[uuid.UUID | None] = mapped_column()
    strategy: Mapped[ChunkingStrategy] = mapped_column(
        str_enum(ChunkingStrategy, "chunking_strategy"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    attributes: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)


class EmbeddingRecord(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, Base):
    """Bookkeeping for a vector stored in Qdrant.

    Qdrant is a derived index: every vector can be rebuilt from chunks.
    """

    __tablename__ = "embedding_records"
    __table_args__ = (
        owned_fk("chunk_id", "document_chunks"),
        UniqueConstraint("chunk_id", "provider", "model"),
        Index("ix_embedding_records_status", "user_id", "status"),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    qdrant_collection: Mapped[str] = mapped_column(String(128), nullable=False)
    qdrant_point_id: Mapped[uuid.UUID] = mapped_column(nullable=False, unique=True)
    status: Mapped[EmbeddingStatus] = mapped_column(
        str_enum(EmbeddingStatus, "embedding_record_status"),
        nullable=False,
        default=EmbeddingStatus.PENDING,
    )
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
