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


# -- email + password ---------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    display_name: str | None = Field(default=None, max_length=200)


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class MfaLoginRequest(BaseModel):
    mfa_token: str = Field(min_length=16, max_length=128)
    code: str = Field(
        min_length=6, max_length=32, description="Authenticator code or a recovery code"
    )


class PasswordLoginResponse(BaseModel):
    mfa_required: bool = False
    mfa_token: str | None = Field(
        default=None, description="Short-lived ticket for POST /auth/login/mfa"
    )
    session: SessionResponse | None = None


class SecurityOverview(BaseModel):
    has_password: bool
    email_verified: bool
    password_changed_at: datetime | None
    totp_enabled: bool
    recovery_codes_remaining: int


class ChangePasswordRequest(BaseModel):
    current_password: str | None = Field(
        default=None, max_length=256, description="Required when a password is already set"
    )
    new_password: str = Field(min_length=1, max_length=256)


class StepUpRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class TotpSetupResponse(BaseModel):
    secret: str = Field(description="Base32 secret for manual entry")
    otpauth_uri: str = Field(description="otpauth:// URI to show as a QR code")


class TotpCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class TotpDisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    code: str = Field(min_length=6, max_length=32)


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str] = Field(description="Shown once. Each works a single time.")
