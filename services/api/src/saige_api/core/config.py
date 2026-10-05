"""Typed application settings loaded from the environment.

`.env` files are a local-development convenience. In production every value
must be injected by the platform's secret manager.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from saige_ai.policy import AIProcessingPolicy

__all__ = ["AIProcessingPolicy", "Environment", "Settings", "get_settings"]


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_json: bool = True
    api_public_url: str = "http://localhost:8000"
    web_public_url: str = "http://localhost:3000"
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # MongoDB connection string. The database name comes from the URI path
    # (e.g. ...mongodb.net/saige_vault?...) and defaults to "saige_vault".
    mongodb_uri: SecretStr = SecretStr("mongodb://localhost:27017/saige_vault")

    # Cloudflare R2 (S3-compatible). Without these, uploads are unavailable
    # (development and tests can use the in-memory store instead).
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: SecretStr | None = None
    r2_bucket: str | None = None
    # Override the endpoint (e.g. a local S3-compatible server). Defaults to
    # https://<account_id>.r2.cloudflarestorage.com
    r2_endpoint: str | None = None
    # Development/test only: keep files in memory when R2 isn't configured.
    memory_storage: bool = False
    # Without R2/S3 settings, file content is stored in MongoDB (GridFS).
    # Set to false to disable uploads unless R2/S3 is configured.
    mongodb_file_storage: bool = True

    # Optional. Without Redis, short-lived state is kept in-process, which is
    # only correct for a single API instance (fine for one free container).
    redis_url: str | None = None

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None

    jwt_secret: SecretStr | None = None
    token_encryption_key: SecretStr | None = None

    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    # Must point at the web origin (proxied to the API) so session cookies
    # are first-party, e.g. http://localhost:3000/api/v1/auth/google/callback
    google_redirect_uri: str | None = None

    access_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    refresh_token_ttl_days: int = Field(default=30, ge=1, le=90)
    # Secure cookies require HTTPS; defaults to True in production.
    cookie_secure: bool | None = None
    # Development-only email login (no Google). Refused in production.
    dev_login_enabled: bool = False
    auth_rate_limit_per_minute: int = Field(default=20, ge=1)
    # Email + password sign-in (Argon2id, optional TOTP). On by default.
    password_login_enabled: bool = True
    # Reject passwords seen in data breaches (Have I Been Pwned, k-anonymity:
    # only the first 5 hex characters of a SHA-1 hash are sent).
    password_breach_check: bool = True
    registrations_per_hour_per_ip: int = Field(default=10, ge=1)

    max_upload_bytes: int = Field(default=100 * 1024 * 1024, ge=1024, le=5 * 1024**3)
    upload_rate_limit_per_minute: int = Field(default=120, ge=1)

    ai_processing_policy: AIProcessingPolicy = AIProcessingPolicy.DISABLED

    # Generous: serverless databases (e.g. Neon free tier) take seconds to wake.
    readiness_timeout_seconds: float = 8.0
    worker_heartbeat_max_age_seconds: int = 60

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator(
        "qdrant_api_key",
        "jwt_secret",
        "token_encryption_key",
        "google_client_secret",
        "cookie_secure",
        "redis_url",
        "r2_secret_access_key",
        "r2_account_id",
        "r2_access_key_id",
        "r2_bucket",
        "r2_endpoint",
        mode="before",
    )
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("token_encryption_key")
    @classmethod
    def _valid_encryption_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            from saige_api.crypto import decode_key  # noqa: PLC0415 - avoid import cycle

            decode_key(value.get_secret_value())
        return value

    @model_validator(mode="after")
    def _enforce_production_requirements(self) -> Settings:
        if self.app_env is not Environment.PRODUCTION:
            return self
        missing = [
            name
            for name, value in (
                ("JWT_SECRET", self.jwt_secret),
                ("TOKEN_ENCRYPTION_KEY", self.token_encryption_key),
            )
            if value is None
        ]
        if missing:
            raise ValueError(f"Missing required production settings: {', '.join(missing)}")
        if self.jwt_secret is not None and len(self.jwt_secret.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters in production")
        if "*" in self.cors_allowed_origins:
            raise ValueError("Wildcard CORS origins are not allowed in production")
        if self.dev_login_enabled:
            raise ValueError("DEV_LOGIN_ENABLED must not be set in production")
        if self.cookie_secure is False:
            raise ValueError("COOKIE_SECURE cannot be disabled in production")
        if self.memory_storage:
            raise ValueError("MEMORY_STORAGE is for development only")
        return self

    @property
    def secure_cookies(self) -> bool:
        return self.cookie_secure if self.cookie_secure is not None else self.is_production

    @property
    def r2_configured(self) -> bool:
        return bool(
            self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket
            and (self.r2_endpoint or self.r2_account_id)
        )

    @property
    def storage_available(self) -> bool:
        return (
            self.r2_configured
            or (self.memory_storage and not self.is_production)
            or self.mongodb_file_storage
        )

    @property
    def google_oauth_configured(self) -> bool:
        return bool(
            self.google_client_id and self.google_client_secret and self.google_redirect_uri
        )

    @property
    def is_production(self) -> bool:
        return self.app_env is Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    return Settings()
