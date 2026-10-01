"""Audit, security events, notifications, sync and feature flags."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import INET
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
    ActorType,
    AuditAction,
    NotificationType,
    SecuritySeverity,
    SyncChangeType,
    SyncStatus,
    SyncType,
)


class AuditLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only audit trail.

    user_id is nullable (SET NULL) so the trail survives account deletion and
    can record events before a user is known (e.g. a failed login).
    `details` must never contain secrets, tokens or document content.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_action_created", "action", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_type: Mapped[ActorType] = mapped_column(
        str_enum(ActorType, "audit_actor_type"), nullable=False
    )
    action: Mapped[AuditAction] = mapped_column(
        str_enum(AuditAction, "audit_action"), nullable=False
    )
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[uuid.UUID | None] = mapped_column()
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    request_id: Mapped[str | None] = mapped_column(String(128))
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(512))
    details: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)


class SecurityEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_user_created", "user_id", "created_at"),
        Index(
            "ix_security_events_unresolved",
            "severity",
            postgresql_where=text("resolved_at IS NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[SecuritySeverity] = mapped_column(
        str_enum(SecuritySeverity, "security_severity"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(128))
    ip_address: Mapped[str | None] = mapped_column(INET)
    details: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(UUIDPrimaryKeyMixin, UserOwnedMixin, CreatedAtMixin, Base):
    """In-app / push notification. `title` and `body` are written to be safe
    for lock-screen previews: no document content by default."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notifications_user_unread",
            "user_id",
            "created_at",
            postgresql_where=text("read_at IS NULL"),
        ),
    )

    type: Mapped[NotificationType] = mapped_column(
        str_enum(NotificationType, "notification_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(String(1000))
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[uuid.UUID | None] = mapped_column()
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncJob(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "sync_jobs"
    __table_args__ = (
        tenant_key("sync_jobs"),
        owned_fk("storage_connection_id", "storage_connections"),
        Index("ix_sync_jobs_connection_created", "storage_connection_id", "created_at"),
    )

    storage_connection_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    sync_type: Mapped[SyncType] = mapped_column(str_enum(SyncType, "sync_type"), nullable=False)
    status: Mapped[SyncStatus] = mapped_column(
        str_enum(SyncStatus, "sync_status"), nullable=False, default=SyncStatus.QUEUED
    )
    start_page_token: Mapped[str | None] = mapped_column(String(255))
    end_page_token: Mapped[str | None] = mapped_column(String(255))
    stats: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncEvent(UUIDPrimaryKeyMixin, UserOwnedMixin, CreatedAtMixin, Base):
    __tablename__ = "sync_events"
    __table_args__ = (
        owned_fk("sync_job_id", "sync_jobs"),
        owned_fk("file_id", "files", ondelete="SET NULL"),
        Index("ix_sync_events_job", "sync_job_id"),
    )

    sync_job_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    change_type: Mapped[SyncChangeType] = mapped_column(
        str_enum(SyncChangeType, "sync_change_type"), nullable=False
    )
    storage_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    file_id: Mapped[uuid.UUID | None] = mapped_column()
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))


class FeatureFlag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Global flag (user_id NULL) or a per-user override."""

    __tablename__ = "feature_flags"
    __table_args__ = (UniqueConstraint("key", "user_id", postgresql_nulls_not_distinct=True),)

    key: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    rules: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)


# Tables intentionally exempt from the "non-null user_id" tenancy rule.
# Enforced by tests/security/test_tenant_isolation_schema.py.
GLOBAL_OR_NULLABLE_USER_TABLES = frozenset(
    {"users", "audit_logs", "security_events", "feature_flags"}
)
