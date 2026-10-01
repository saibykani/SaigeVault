"""Auth request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from saige_api.models.enums import ClientPlatform


class UserProfile(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    avatar_url: str | None


class SessionResponse(BaseModel):
    user: UserProfile
    session_id: uuid.UUID
    access_expires_at: datetime


class SessionSummary(BaseModel):
    id: uuid.UUID = Field(description="Session (family) id; stable across token refreshes")
    platform: ClientPlatform
    user_agent: str | None
    ip_address: str | None
    started_at: datetime
    last_seen_at: datetime | None
    expires_at: datetime
    current: bool


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]


class DevLoginRequest(BaseModel):
    email: EmailStr
    display_name: str | None = Field(default=None, max_length=200)


class RefreshRequest(BaseModel):
    """Body form for non-browser clients. Browsers send the refresh cookie instead."""

    refresh_token: str | None = Field(default=None, max_length=256)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth token type, not a secret
    expires_in: int


class RefreshResponse(BaseModel):
    session_id: uuid.UUID
    access_expires_at: datetime
    tokens: TokenPair | None = Field(
        default=None, description="Only returned when the refresh token was sent in the body"
    )
