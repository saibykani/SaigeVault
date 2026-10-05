"""Run the real Saige API against fake Google and in-memory file storage, for browser tests.

TEST TOOLING ONLY — never deploy. Uses a dedicated test MongoDB database.

    uv run python tests/e2e/fake_stack.py --web http://localhost:3101 --port 8010
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api" / "tests"))

from google_fake import CLIENT_ID, FakeGoogle  # noqa: E402

from saige_api.auth.google import GoogleOAuthClient  # noqa: E402
from saige_api.core.config import Environment, Settings  # noqa: E402
from saige_api.crypto import generate_key  # noqa: E402
from saige_api.main import create_app  # noqa: E402
from saige_api.resources import Resources  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://localhost:3101")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--mongodb-uri", default="mongodb://127.0.0.1:27017/saige_e2e_test")
    parser.add_argument("--redis-url", default="")
    args = parser.parse_args()
    if "test" not in args.mongodb_uri.split("?", 1)[0].rsplit("/", 1)[-1]:
        sys.exit("refusing to run against a non-test database")

    google = FakeGoogle()
    google.identity.update(email="e2e@example.com", sub="e2e-google-sub")
    values: dict[str, Any] = {
        "app_env": Environment.DEVELOPMENT,
        "log_json": False,
        "mongodb_uri": args.mongodb_uri,
        "redis_url": args.redis_url,
        "memory_storage": True,
        "jwt_secret": "e2e-" + "x" * 44,
        "token_encryption_key": generate_key(),
        "web_public_url": args.web,
        "google_client_id": CLIENT_ID,
        "google_client_secret": "e2e-secret",
        "google_redirect_uri": f"{args.web}/api/v1/auth/google/callback",
        "dev_login_enabled": True,
        "auth_rate_limit_per_minute": 1000,
        "upload_rate_limit_per_minute": 1000,
        "password_breach_check": False,  # no real network in e2e
    }
    settings = Settings(_env_file=None, **values)  # type: ignore[call-arg]

    def factory(s: Settings) -> Resources:
        resources = Resources.create(s)
        resources.external_http = httpx.AsyncClient(transport=google.transport())
        resources.google = GoogleOAuthClient(
            client_id=CLIENT_ID,
            client_secret="e2e-secret",
            redirect_uri=s.google_redirect_uri or "",
            http=resources.external_http,
        )
        return resources

    uvicorn.run(create_app(settings, resource_factory=factory), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
