from __future__ import annotations

import pytest
from pydantic import ValidationError
from support import TEST_KEY, make_settings

from saige_api.core.config import AIProcessingPolicy, Environment


def test_defaults_are_safe() -> None:
    settings = make_settings()
    assert settings.ai_processing_policy is AIProcessingPolicy.DISABLED
    assert settings.is_production is False


def test_cors_origins_parsed_from_comma_separated_string() -> None:
    settings = make_settings(cors_allowed_origins="http://a.test, http://b.test")
    assert settings.cors_allowed_origins == ["http://a.test", "http://b.test"]


def test_production_requires_secrets() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        make_settings(app_env=Environment.PRODUCTION)


def test_production_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        make_settings(
            app_env=Environment.PRODUCTION, jwt_secret="short", token_encryption_key=TEST_KEY
        )


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="Wildcard"):
        make_settings(
            app_env=Environment.PRODUCTION,
            jwt_secret="x" * 48,
            token_encryption_key=TEST_KEY,
            cors_allowed_origins="*",
        )


def test_secrets_are_not_rendered_in_repr() -> None:
    settings = make_settings(jwt_secret="very-secret-jwt-value")
    assert "very-secret-jwt-value" not in repr(settings)


def test_empty_cookie_secure_means_automatic() -> None:
    assert make_settings(cookie_secure="").secure_cookies is False
    assert make_settings(cookie_secure="true").secure_cookies is True


def test_production_rejects_dev_login() -> None:
    with pytest.raises(ValidationError, match="DEV_LOGIN_ENABLED"):
        make_settings(
            app_env=Environment.PRODUCTION,
            jwt_secret="x" * 48,
            token_encryption_key=TEST_KEY,
            dev_login_enabled=True,
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.neon.tech/neondb?ssl=require",
        ),
        (
            "postgres://u:p@db.example.com:5432/app",
            "postgresql+asyncpg://u:p@db.example.com:5432/app",
        ),
        ("postgresql+asyncpg://u:p@localhost/db", "postgresql+asyncpg://u:p@localhost/db"),
    ],
)
def test_hosted_database_urls_are_normalized(raw: str, expected: str) -> None:
    assert make_settings(database_url=raw).database_url == expected


def test_non_postgres_database_url_rejected() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        make_settings(database_url="mysql://u:p@localhost/db")


def test_redis_is_off_unless_configured() -> None:
    """Hosts without Redis (single free instance) must not fall back to localhost."""
    assert make_settings().redis_url is None
    assert make_settings(redis_url="").redis_url is None
    assert make_settings(redis_url="rediss://default:x@h.upstash.io:6379").redis_url
