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

    database_url: str = "postgresql+asyncpg://saige:saige@localhost:5432/saige_vault"
    database_pool_size: int = 10
    database_max_overflow: int = 10

    redis_url: str = "redis://localhost:6379/0"

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None

    jwt_secret: SecretStr | None = None
    token_encryption_key: SecretStr | None = None

    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str | None = None

    ai_processing_policy: AIProcessingPolicy = AIProcessingPolicy.DISABLED

    readiness_timeout_seconds: float = 2.0
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
        mode="before",
    )
    @classmethod
    def _empty_secret_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg:// driver")
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
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env is Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    return Settings()
