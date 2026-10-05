"""Run the real Saige API against fake Google + fake Drive, for browser end-to-end tests.

TEST TOOLING ONLY — never deploy. Uses a dedicated test database and Redis DB.

    uv run python tests/e2e/fake_stack.py --web http://localhost:3101 --port 8010

The fake Google auto-approves consent: the browser test intercepts the
redirect to accounts.google.com and sends the *nonce* back as the code.
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

from drive_fake import FakeDrive  # noqa: E402
from google_fake import CLIENT_ID, FakeGoogle  # noqa: E402

from saige_api.auth.google import TOKEN_ENDPOINT, GoogleOAuthClient  # noqa: E402
from saige_api.core.config import Environment, Settings  # noqa: E402
from saige_api.crypto import generate_key  # noqa: E402
from saige_api.main import create_app  # noqa: E402
from saige_api.resources import Resources  # noqa: E402


class AutoApproveGoogle(FakeGoogle):
    """Treats the authorization code as the nonce, so any consent 'succeeds'."""

    def handler(self, request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(TOKEN_ENDPOINT):
            from urllib.parse import parse_qs  # noqa: PLC0415

            form = parse_qs(request.content.decode())
            code = form.get("code", [""])[0]
            if code:
                self.codes[code] = code
        return super().handler(request)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://localhost:3101")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument(
        "--database-url",
        default="postgresql+asyncpg://saige:change-me-local-only@127.0.0.1:5432/saige_e2e_test",
    )
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6379/14")
    args = parser.parse_args()
    if "test" not in args.database_url.rsplit("/", 1)[-1]:
        sys.exit("refusing to run against a non-test database")

    google = AutoApproveGoogle(
        granted_scope="openid email https://www.googleapis.com/auth/drive.file",
        issue_refresh_token=True,
    )
    google.identity.update(email="e2e@example.com", sub="e2e-google-sub")
    drive = FakeDrive()
    values: dict[str, Any] = {
        "app_env": Environment.DEVELOPMENT,
        "log_json": False,
        "database_url": args.database_url,
        "redis_url": args.redis_url,
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
        resources.external_http = httpx.AsyncClient(transport=google.transport(drive))
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
