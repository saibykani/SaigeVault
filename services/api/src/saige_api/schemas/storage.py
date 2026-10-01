"""Storage connection response models. Credentials are never included."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from saige_api.models.enums import StorageConnectionStatus, StorageProviderKind


class StorageConnectionSummary(BaseModel):
    id: uuid.UUID
    provider: StorageProviderKind
    account_email: str | None
    status: StorageConnectionStatus
    scopes: list[str]
    connected_at: datetime
    disconnected_at: datetime | None
    last_synced_at: datetime | None


class StorageConnectionListResponse(BaseModel):
    connections: list[StorageConnectionSummary]


class StorageQuotaResponse(BaseModel):
    limit_bytes: int | None
    usage_bytes: int
    usage_in_drive_bytes: int | None
    usage_in_trash_bytes: int | None


class DisconnectResponse(BaseModel):
    revoked_at_provider: bool
