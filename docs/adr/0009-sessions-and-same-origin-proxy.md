# ADR-0009: Rotating refresh-token sessions behind a same-origin proxy

**Status:** Accepted · **Date:** 2026-10-01

## Context

The web client needs sessions that resist XSS token theft, CSRF and token replay. It must also work when the web app and API live on different hosts (e.g. Vercel + a VM), where third-party cookies are blocked by browsers.

## Decision

- **Same-origin proxy.** The browser only talks to the web origin. Next.js rewrites `/api/*`, `/health` and `/ready` to the API (`API_PROXY_TARGET`, set at build time). Session cookies are therefore first-party. Google's OAuth redirect URI points at the web origin too.
- **Tokens:**
  - **Access token:** HS256 JWT, 15 minutes, claims `sub` and `sid` (the session family). Every request also checks that the session is still active in PostgreSQL, so sign-out and revocation take effect immediately.
  - **Refresh token:** 384-bit random value stored only as a SHA-256 hash. Each use rotates it. The presented row becomes `rotated` and a new row joins the same `family_id`.
  - **Reuse detection:** presenting an already-rotated token more than 20 seconds after rotation revokes the whole family and records a `refresh_token_reuse` security event. Inside the 20-second window it is treated as a benign multi-tab race and nothing is revoked.
- **Cookies** (web):
  - `saige_access`: HttpOnly, path `/api`.
  - `saige_refresh`: HttpOnly, path `/api/v1/auth`, so it is only ever sent to auth routes.
  - `saige_csrf`: readable, path `/`.
  - All three are `SameSite=Lax`, and `Secure` outside local development.
- **CSRF:** double-submit. For cookie-authenticated unsafe methods, the `X-CSRF-Token` header must equal the `saige_csrf` cookie. Bearer-authenticated clients (mobile, API) are exempt because browsers never attach bearer tokens automatically.
- **Google sign-in:** Authorization Code + PKCE (S256), single-use `state` (Redis `GETDEL`, 10-minute TTL) and `nonce`. The ID token is verified against Google's JWKS (issuer, audience, expiry, nonce, `email_verified`). Login requests only `openid email profile`; Drive access is a separate consent in Phase 4.
- **Development sign-in** (`DEV_LOGIN_ENABLED`) exists for local use without Google credentials. Settings validation refuses it in production, and the route returns 404 when disabled.

## Consequences

- The UI route guard (`apps/web/src/proxy.ts`) only checks for the presence of `saige_csrf`. It is a UX convenience; authorization always happens in the API.
- Next.js rewrites forward client-supplied `X-Forwarded-For` unchanged, so the API does **not** trust that header by default. Until a trusted reverse proxy sets it, audit IPs and rate-limit keys reflect the web server's address.
- Access-token revocation costs one indexed query per request, which is acceptable for a personal vault.
