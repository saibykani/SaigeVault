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


def normalize_database_url(value: str) -> str:
    """Accept URLs exactly as hosted providers (Neon, Supabase, Render) print them.

    - postgres:// and postgresql:// become postgresql+asyncpg://
    - libpq's sslmode=... becomes asyncpg's ssl=...
    - libpq-only options asyncpg rejects (channel_binding, ...) are dropped
    """
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit  # noqa: PLC0415

    url = value.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix) :]
    if not url.startswith("postgresql+asyncpg://"):
        raise ValueError("DATABASE_URL must be a PostgreSQL URL (postgresql://...)")
    parts = urlsplit(url)
    query: list[tuple[str, str]] = []
    for key, val in parse_qsl(parts.query, keep_blank_values=True):
        if key == "sslmode":
            if val in {"require", "verify-ca", "verify-full", "prefer", "allow"}:
                query.append(("ssl", val))
        elif key in {"channel_binding", "options", "application_name", "target_session_attrs"}:
            continue
        else:
            query.append((key, val))
    return urlunsplit(parts._replace(query=urlencode(query)))


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

    database_url: str = "postgresql+asyncpg://saige:saige@localhost:5432/saige_vault"
    database_pool_size: int = 10
    database_max_overflow: int = 10

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

    # Least privilege by default: Saige only sees files it created (its own
    # "Saige Vault" folder), never the rest of the user's Drive.
    google_drive_scope: str = "https://www.googleapis.com/auth/drive.file"
    max_upload_bytes: int = Field(default=100 * 1024 * 1024, ge=1024, le=5 * 1024**3)
    upload_rate_limit_per_minute: int = Field(default=120, ge=1)
    google_drive_root_folder_name: str = Field(default="Saige Vault", min_length=1, max_length=100)

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

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, value: str) -> str:
        return normalize_database_url(value)

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
        return self

    @property
    def secure_cookies(self) -> bool:
        return self.cookie_secure if self.cookie_secure is not None else self.is_production

    @property
    def google_drive_available(self) -> bool:
        return self.google_oauth_configured and self.token_encryption_key is not None

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
