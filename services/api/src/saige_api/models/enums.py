"""Domain enumerations shared by the API, the worker and API clients."""

from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ClientPlatform(StrEnum):
    WEB = "web"
    ANDROID = "android"
    IOS = "ios"
    API = "api"


class StorageProviderKind(StrEnum):
    GOOGLE_DRIVE = "google_drive"


class StorageConnectionStatus(StrEnum):
    ACTIVE = "active"
    NEEDS_REAUTH = "needs_reauth"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class FileVisibility(StrEnum):
    PRIVATE = "private"


class ProcessingStatus(StrEnum):
    """Overall lifecycle of a file through the processing pipeline."""

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class StageStatus(StrEnum):
    """Status of a single pipeline stage (OCR, extraction, embedding)."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED_BY_POLICY = "skipped_by_policy"


class DocumentType(StrEnum):
    IDENTITY = "identity"
    EDUCATION = "education"
    EMPLOYMENT = "employment"
    SALARY = "salary"
    BANKING = "banking"
    TAX = "tax"
    INSURANCE = "insurance"
    FINANCE = "finance"
    MEDICAL = "medical"
    LEGAL = "legal"
    TRAVEL = "travel"
    CERTIFICATE = "certificate"
    RESUME = "resume"
    JOB_DESCRIPTION = "job_description"
    PERSONAL = "personal"
    WORK = "work"
    PROJECT = "project"
    IMAGE = "image"
    OTHER = "other"
    UNCLASSIFIED = "unclassified"


class DataSource(StrEnum):
    """Provenance of a piece of metadata. AI output is never authoritative."""

    SYSTEM = "system"
    AI = "ai"
    USER = "user"


class TagStatus(StrEnum):
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class JobType(StrEnum):
    DOCUMENT_PROCESSING = "document_processing"
    OCR = "ocr"
    EMBEDDING_GENERATION = "embedding_generation"
    METADATA_EXTRACTION = "metadata_extraction"
    THUMBNAIL_GENERATION = "thumbnail_generation"
    DRIVE_SYNC = "drive_sync"
    FILE_INTEGRITY_CHECK = "file_integrity_check"
    AI_INDEXING = "ai_indexing"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"
    CANCELLED = "cancelled"


class ExtractionMethod(StrEnum):
    NATIVE_TEXT = "native_text"
    OCR = "ocr"


class SummaryType(StrEnum):
    SHORT = "short"
    DETAILED = "detailed"
    KEY_POINTS = "key_points"
    ACTION_ITEMS = "action_items"
    IMPORTANT_DATES = "important_dates"


class ChunkingStrategy(StrEnum):
    RECURSIVE = "recursive"
    DOCUMENT_AWARE = "document_aware"
    PAGE_AWARE = "page_aware"
    SEMANTIC = "semantic"


class EmbeddingStatus(StrEnum):
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"
    STALE = "stale"


class ConversationScope(StrEnum):
    FILE = "file"
    FILES = "files"
    FOLDER = "folder"
    COLLECTION = "collection"
    VAULT = "vault"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MessageStatus(StrEnum):
    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    MAX_ITERATIONS = "max_iterations"
    CANCELLED = "cancelled"


class AgentStepType(StrEnum):
    PLAN = "plan"
    TOOL_CALL = "tool_call"
    OBSERVATION = "observation"
    FINAL = "final"


class ToolCallStatus(StrEnum):
    PENDING = "pending"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"


class SearchMode(StrEnum):
    EXACT = "exact"
    FULL_TEXT = "full_text"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class AuditAction(StrEnum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    FILE_UPLOAD = "FILE_UPLOAD"
    FILE_DOWNLOAD = "FILE_DOWNLOAD"
    FILE_DELETE = "FILE_DELETE"
    FILE_RESTORE = "FILE_RESTORE"
    FILE_RENAME = "FILE_RENAME"
    FILE_MOVE = "FILE_MOVE"
    AI_QUERY = "AI_QUERY"
    AI_DOCUMENT_ACCESS = "AI_DOCUMENT_ACCESS"
    AGENT_EXECUTION = "AGENT_EXECUTION"
    OAUTH_CONNECT = "OAUTH_CONNECT"
    OAUTH_DISCONNECT = "OAUTH_DISCONNECT"
    SECURITY_EVENT = "SECURITY_EVENT"
    DATA_EXPORT = "DATA_EXPORT"


class ActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"
    WORKER = "worker"


class SecuritySeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(StrEnum):
    PROCESSING_COMPLETE = "processing_complete"
    PROCESSING_FAILED = "processing_failed"
    UPLOAD_COMPLETE = "upload_complete"
    SYNC_COMPLETE = "sync_complete"
    AI_INDEXING_COMPLETE = "ai_indexing_complete"
    SECURITY_EVENT = "security_event"
    EXPIRY_REMINDER = "expiry_reminder"


class SyncType(StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"


class SyncStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SyncChangeType(StrEnum):
    CREATED = "created"
    MODIFIED = "modified"
    MOVED = "moved"
    RENAMED = "renamed"
    TRASHED = "trashed"
    RESTORED = "restored"
    DELETED = "deleted"
