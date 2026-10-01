"""Users, sessions, OAuth identities, storage connections and API keys."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    DateTime,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from saige_api.db.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UserOwnedMixin,
    UUIDPrimaryKeyMixin,
    owned_fk,
    str_enum,
    tenant_key,
)
from saige_api.models.enums import (
    ClientPlatform,
    StorageConnectionStatus,
    StorageProviderKind,
    UserStatus,
)


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("uq_users_email_lower", text("lower(email)"), unique=True),)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[UserStatus] = mapped_column(
        str_enum(UserStatus, "user_status"), nullable=False, default=UserStatus.ACTIVE
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, Base):
    """A refresh-token family for one device. Only token hashes are stored."""

    __tablename__ = "user_sessions"
    __table_args__ = (
        tenant_key("user_sessions"),
        owned_fk("rotated_from_id", "user_sessions", ondelete="SET NULL"),
        Index("ix_user_sessions_active", "user_id", "revoked_at", "expires_at"),
        Index("ix_user_sessions_family", "user_id", "family_id"),
    )

    # Stable session identifier shared by every rotation of one sign-in.
    family_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    platform: Mapped[ClientPlatform] = mapped_column(
        str_enum(ClientPlatform, "client_platform"), nullable=False
    )
    device_name: Mapped[str | None] = mapped_column(String(200))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip_address: Mapped[str | None] = mapped_column(INET)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(64))
    rotated_from_id: Mapped[uuid.UUID | None] = mapped_column()


class OAuthAccount(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, Base):
    """Login identity at an external identity provider (e.g. Google)."""

    __tablename__ = "oauth_accounts"
    __table_args__ = (UniqueConstraint("provider", "provider_subject"),)

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StorageConnection(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, Base):
    """Authorised link to a user's storage provider account.

    OAuth tokens are encrypted with the application key before storage and
    never leave the backend.
    """

    __tablename__ = "storage_connections"
    __table_args__ = (
        tenant_key("storage_connections"),
        UniqueConstraint("user_id", "provider", "provider_account_id"),
    )

    provider: Mapped[StorageProviderKind] = mapped_column(
        str_enum(StorageProviderKind, "storage_provider_kind"), nullable=False
    )
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    account_email: Mapped[str | None] = mapped_column(String(320))
    status: Mapped[StorageConnectionStatus] = mapped_column(
        str_enum(StorageConnectionStatus, "storage_connection_status"),
        nullable=False,
        default=StorageConnectionStatus.ACTIVE,
    )
    encrypted_access_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    encrypted_refresh_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    token_key_version: Mapped[int] = mapped_column(nullable=False, default=1)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String(255)), nullable=False, default=list)
    root_folder_id: Mapped[str | None] = mapped_column(String(255))
    changes_page_token: Mapped[str | None] = mapped_column(String(255))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiKey(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, Base):
    """Personal access key. Only a hash and a display prefix are stored."""

    __tablename__ = "api_keys"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False, default=list)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
