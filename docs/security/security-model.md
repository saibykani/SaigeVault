# Security model

All documents are treated as **sensitive by default**. This page lists controls that are **implemented** and controls that are **planned**, and never claims more than exists.

## Implemented (foundation)

| Area | Control | Where |
| --- | --- | --- |
| Tenant isolation | `user_id` on every tenant table; composite `(id, user_id)` foreign keys; tests that fail the build on violations | ADR-0005, `tests/security`, `tests/integration` |
| Secrets | No secrets in the repo; `.env` git-ignored; production refuses to start without `JWT_SECRET` (≥32 chars) and `TOKEN_ENCRYPTION_KEY`; `SecretStr` hides values in reprs | `core/config.py` |
| Token storage | OAuth tokens stored only as encrypted bytes; API keys and refresh tokens stored only as hashes | schema |
| Logging | JSON logs with key-based redaction (tokens, passwords, content, OCR text, prompts, queries) and bearer-token scrubbing; access log records the path only; SQL echo disabled | `core/logging.py`, `core/middleware.py` |
| HTTP | Strict API CSP (`default-src 'none'`), `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, COOP/CORP, `Cache-Control: no-store`, HSTS in production; allow-listed CORS; docs disabled in production | `core/middleware.py`, `main.py` |
| Errors | Uniform envelope; internal messages never returned; validation errors drop input values; readiness never leaks driver errors | `core/errors.py`, `health.py` |
| Web | CSP (`frame-ancestors 'none'`, `object-src 'none'`, connect-src limited to the API), security headers, `noindex`; client UI state only in localStorage | `apps/web/next.config.ts` |
| AI privacy | Processing policy defaults to `disabled`; `ensure_allowed()` gate | ADR-0006 |
| iOS | App Lock (Face ID / Touch ID / passcode) on by default; privacy shield in the app switcher; ephemeral `URLSession` with no cache; ATS HTTPS-only (local networking only for development); release builds reject non-HTTPS servers | `apps/ios` |
| Containers | Non-root users; ports bound to 127.0.0.1; secrets via environment, never build args | `infrastructure/docker` |
| Supply chain | Locked dependencies (uv.lock, package-lock.json); CI runs gitleaks, pip-audit, npm audit and CodeQL; Dependabot | `.github` |

## Planned

| Phase | Control |
| --- | --- |
| P3 | Google OAuth (PKCE + state), HttpOnly/Secure/SameSite session cookies for web, Keychain/Keystore tokens for mobile, refresh-token rotation with reuse detection, CSRF tokens for cookie-authenticated mutations, audit `LOGIN`/`LOGOUT` |
| P4 | AES-GCM token encryption with key versioning; least-privilege Drive scopes; `OAUTH_CONNECT`/`OAUTH_DISCONNECT` audit |
| P5 | Upload validation by magic bytes, size limits, type allow-list, filename sanitization, ZIP-bomb protection; rate limiting |
| P7–P12 | Prompt-injection defences (retrieved text as delimited data), retrieval always filtered by `user_id`, tool-call authorization, confirmation for destructive actions |
| P14 | Nonce-based web CSP (removing `'unsafe-inline'`), PostgreSQL Row-Level Security, security-event alerting, Android screenshot protection (`FLAG_SECURE`), encrypted offline caches, penetration-test checklist |

## Threats specific to AI

Untrusted inputs: filenames, client MIME types, metadata, OCR output, LLM output and instructions inside retrieved documents.

| Threat | Defence |
| --- | --- |
| Prompt injection / indirect injection / RAG poisoning | Documents are data, never instructions. Delimited context. System prompt hardening. No tool executes without server-side authorization |
| Cross-user retrieval | Database-level isolation, plus `user_id` filtering in Qdrant |
| Data exfiltration / tool abuse | Narrow tools, no arbitrary code or network tools, confirmation for side effects, bounded result summaries |
| Sensitive leakage | Redacted logs; notifications contain no document content by default |

## Reporting

Report suspected vulnerabilities privately to the repository owner. Do not open public issues for security problems.
