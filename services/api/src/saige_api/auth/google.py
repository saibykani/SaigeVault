"""Google OpenID Connect: authorization URL, code exchange, ID token verification.

Authorization Code flow with PKCE (S256), a single-use `state` and a `nonce`.
Client secrets never leave the backend.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"  # noqa: S105 - URL, not a secret
JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
LOGIN_SCOPES = ("openid", "email", "profile")
JWKS_CACHE_SECONDS = 3600


class GoogleAuthError(Exception):
    """Sign-in failed. `code` is safe to show to users and log."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class PKCEPair:
    verifier: str
    challenge: str

    @classmethod
    def generate(cls) -> PKCEPair:
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return cls(verifier=verifier, challenge=challenge)


@dataclass(frozen=True, slots=True)
class GoogleIdentity:
    subject: str
    email: str
    email_verified: bool
    name: str | None
    picture: str | None


@dataclass(frozen=True, slots=True)
class GoogleTokens:
    access_token: str
    expires_in: int
    scopes: tuple[str, ...]
    refresh_token: str | None = None
    id_token: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> GoogleTokens:
        access = payload.get("access_token")
        if not isinstance(access, str) or not access:
            raise GoogleAuthError("missing_access_token")
        refresh = payload.get("refresh_token")
        id_token = payload.get("id_token")
        return cls(
            access_token=access,
            expires_in=int(payload.get("expires_in", 3600)),
            scopes=tuple(str(payload.get("scope", "")).split()),
            refresh_token=refresh if isinstance(refresh, str) and refresh else None,
            id_token=id_token if isinstance(id_token, str) else None,
        )


class GoogleOAuthClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        http: httpx.AsyncClient,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._http = http
        self._jwks: jwt.PyJWKSet | None = None
        self._jwks_fetched_at = 0.0

    def authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_challenge: str,
        scopes: tuple[str, ...] = LOGIN_SCOPES,
        offline: bool = False,
        login_hint: str | None = None,
    ) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            # Offline access (refresh token) needs explicit consent each time
            # so Google reliably returns a refresh token.
            "prompt": "consent" if offline else "select_account",
            "access_type": "offline" if offline else "online",
        }
        if offline:
            params["include_granted_scopes"] = "false"
        if login_hint:
            params["login_hint"] = login_hint
        return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    async def _token_request(
        self, data: dict[str, str], error_code: str, *, invalid_grant_code: str | None = None
    ) -> dict[str, Any]:
        try:
            response = await self._http.post(
                TOKEN_ENDPOINT,
                data={"client_id": self._client_id, "client_secret": self._client_secret, **data},
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise GoogleAuthError("google_unreachable") from exc
        if response.status_code != 200:
            body = (
                response.json()
                if response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            if body.get("error") == "invalid_grant":
                raise GoogleAuthError(invalid_grant_code or error_code)
            raise GoogleAuthError(error_code)
        payload: dict[str, Any] = response.json()
        return payload

    async def exchange_code_for_tokens(self, code: str, code_verifier: str) -> GoogleTokens:
        payload = await self._token_request(
            {
                "code": code,
                "redirect_uri": self._redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
            "code_exchange_failed",
        )
        return GoogleTokens.from_payload(payload)

    async def exchange_code(self, code: str, code_verifier: str) -> str:
        """Sign-in: returns only the ID token. Login access tokens are discarded."""
        tokens = await self.exchange_code_for_tokens(code, code_verifier)
        if tokens.id_token is None:
            raise GoogleAuthError("missing_id_token")
        return tokens.id_token

    async def refresh_access_token(self, refresh_token: str) -> GoogleTokens:
        payload = await self._token_request(
            {"grant_type": "refresh_token", "refresh_token": refresh_token},
            "refresh_failed",
            # The user revoked access or the token expired: reconnect required.
            invalid_grant_code="invalid_grant",
        )
        return GoogleTokens.from_payload(payload)

    async def revoke(self, token: str) -> bool:
        """Best effort: returns False if Google could not be reached or refused."""
        try:
            response = await self._http.post(REVOKE_ENDPOINT, data={"token": token})
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    async def verify_id_token(self, id_token: str, *, nonce: str) -> GoogleIdentity:
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.PyJWTError as exc:
            raise GoogleAuthError("invalid_id_token") from exc
        key = await self._signing_key(str(header.get("kid", "")))
        try:
            claims: dict[str, Any] = jwt.decode(
                id_token,
                key,
                algorithms=["RS256"],
                audience=self._client_id,
                issuer=ISSUERS,
                leeway=30,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise GoogleAuthError("invalid_id_token") from exc
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise GoogleAuthError("nonce_mismatch")
        email = claims.get("email")
        if not isinstance(email, str) or "@" not in email:
            raise GoogleAuthError("email_missing")
        if claims.get("email_verified") is not True:
            raise GoogleAuthError("email_not_verified")
        return GoogleIdentity(
            subject=str(claims["sub"]),
            email=email,
            email_verified=True,
            name=claims.get("name") if isinstance(claims.get("name"), str) else None,
            picture=claims.get("picture") if isinstance(claims.get("picture"), str) else None,
        )

    async def _signing_key(self, kid: str) -> Any:
        for force in (False, True):  # refetch once in case Google rotated keys
            jwks = await self._load_jwks(force=force)
            for jwk in jwks.keys:
                if jwk.key_id == kid:
                    return jwk.key
        raise GoogleAuthError("unknown_signing_key")

    async def _load_jwks(self, *, force: bool) -> jwt.PyJWKSet:
        fresh = time.monotonic() - self._jwks_fetched_at < JWKS_CACHE_SECONDS
        if self._jwks is not None and fresh and not force:
            return self._jwks
        try:
            response = await self._http.get(JWKS_URI)
            response.raise_for_status()
            self._jwks = jwt.PyJWKSet.from_dict(response.json())
        except (httpx.HTTPError, jwt.PyJWTError, ValueError) as exc:
            raise GoogleAuthError("jwks_unavailable") from exc
        self._jwks_fetched_at = time.monotonic()
        return self._jwks
