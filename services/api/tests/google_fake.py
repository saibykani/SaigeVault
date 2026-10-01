"""A fake Google OIDC provider for tests: RSA-signed ID tokens, JWKS, token endpoint."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from saige_api.auth.google import JWKS_URI, REVOKE_ENDPOINT, TOKEN_ENDPOINT

CLIENT_ID = "test-client.apps.googleusercontent.com"
KID = "test-key-1"


@dataclass
class FakeGoogle:
    private_key: rsa.RSAPrivateKey = field(
        default_factory=lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048)
    )
    # Claims for the next issued ID token. `nonce` is filled from the code map.
    identity: dict[str, Any] = field(
        default_factory=lambda: {
            "sub": "google-sub-1",
            "email": "alice@example.com",
            "email_verified": True,
            "name": "Alice Example",
        }
    )
    nonce_override: str | None = None
    codes: dict[str, str] = field(default_factory=dict)  # code -> nonce
    token_requests: list[dict[str, list[str]]] = field(default_factory=list)
    # Drive consent simulation.
    granted_scope: str = "openid email profile"
    issue_refresh_token: bool = False
    access_token: str = "drive-access-1"
    refresh_tokens: set[str] = field(default_factory=set)
    revoked: list[str] = field(default_factory=list)

    def jwks(self) -> dict[str, Any]:
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.private_key.public_key()))
        public.update({"kid": KID, "alg": "RS256", "use": "sig"})
        return {"keys": [public]}

    def id_token(self, nonce: str, **overrides: Any) -> str:
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "aud": CLIENT_ID,
            "iat": now,
            "exp": now + 600,
            "nonce": nonce,
            **self.identity,
            **overrides,
        }
        return jwt.encode(claims, self.private_key, algorithm="RS256", headers={"kid": KID})

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(JWKS_URI):
            return httpx.Response(200, json=self.jwks())
        if url.startswith(REVOKE_ENDPOINT):
            token = parse_qs(request.content.decode()).get("token", [""])[0]
            self.revoked.append(token)
            self.refresh_tokens.discard(token)
            return httpx.Response(200)
        if url.startswith(TOKEN_ENDPOINT):
            form = parse_qs(request.content.decode())
            self.token_requests.append(form)
            if form.get("grant_type") == ["refresh_token"]:
                if form.get("refresh_token", [""])[0] not in self.refresh_tokens:
                    return httpx.Response(400, json={"error": "invalid_grant"})
                return httpx.Response(
                    200,
                    json={
                        "access_token": self.access_token,
                        "expires_in": 3599,
                        "scope": self.granted_scope,
                    },
                )
            code = form.get("code", [""])[0]
            if code not in self.codes or not form.get("code_verifier"):
                return httpx.Response(400, json={"error": "invalid_grant"})
            nonce = self.nonce_override or self.codes.pop(code)
            body: dict[str, Any] = {
                "access_token": self.access_token,
                "expires_in": 3599,
                "scope": self.granted_scope,
                "id_token": self.id_token(nonce),
            }
            if self.issue_refresh_token:
                refresh = f"1//refresh-{len(self.refresh_tokens) + 1}"
                self.refresh_tokens.add(refresh)
                body["refresh_token"] = refresh
            return httpx.Response(200, json=body)
        return httpx.Response(404)

    def transport(self, drive: Any = None) -> httpx.MockTransport:
        """Optionally route Drive API calls to a FakeDrive on the same transport."""

        def route(request: httpx.Request) -> httpx.Response:
            if drive is not None and drive.handles(str(request.url)):
                return drive.handler(request)  # type: ignore[no-any-return]
            return self.handler(request)

        return httpx.MockTransport(route)
