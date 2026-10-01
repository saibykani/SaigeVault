# System architecture

> Status markers: **Built** = implemented and tested. **Planned (Pn)** = designed, ships in phase *n*.

## Components

```text
            Web (Next.js)      iOS (SwiftUI)      Android (Compose)
                  \                 |                  /
                   \______ HTTPS / REST /api/v1 ______/
                                    |
                           API (FastAPI, Python)
                     /         |            |         \
             PostgreSQL      Redis       Qdrant     Google Drive
             metadata,     queue +      vectors     original files
             audit, RAG   heartbeat   (derived)    (source of truth)
                               |
                         Worker (SAQ)
                 processing · OCR · embeddings · sync
                               |
                    AI layer (saige_ai protocols)
              LLM · Embeddings · Reranker · OCR providers
```

| Component | Path | Status |
| --- | --- | --- |
| API service | `services/api` | **Built:** app factory, config, structured logging with redaction, request IDs, security headers, error envelope, `/health`, `/ready`, `/api/v1/system/info` |
| Database schema | `services/api/src/saige_api/models`, `database/migrations` | **Built:** 31 tables, migrations `0001`–`0002` |
| Worker | `services/worker` | **Built:** SAQ worker, heartbeat, retry policy. Job handlers are Planned (P7, P13) |
| AI layer | `services/ai` | **Built:** provider protocols, processing-policy gate. Adapters are Planned (P9–P11) |
| Auth | `services/api/src/saige_api/auth` | **Built (P3):** Google OIDC, rotating sessions, CSRF, rate limits, audit (ADR-0009) |
| Storage | `services/api/src/saige_api/storage` | **Built (P4):** `StorageProvider` interface, Google Drive provider (folders, list, multipart and resumable upload, streaming download, rename, move, trash/restore, delete, revisions, change tokens, quota), encrypted connections (ADR-0010) |
| Web | `apps/web` | **Built:** app shell, all primary screens, command palette, themes, live system status, sign-in, account menu, session management |
| iOS | `apps/ios` | **Built:** app shell, tabs, App Lock, privacy shield, live server status |
| Android | `apps/android` | In progress |
| Shared TS packages | `packages/*` | **Built:** generated API client and enums, formatting utilities |

## Request lifecycle (API)

1. `RequestContextMiddleware` assigns or validates `X-Request-ID`, binds it to the log context, and emits a path-only access log. Query strings are never logged.
2. `SecurityHeadersMiddleware` adds CSP, `nosniff`, `DENY` framing, `no-referrer`, `no-store`, and HSTS in production.
3. CORS allows only `CORS_ALLOWED_ORIGINS`. A wildcard is rejected in production.
4. Errors are rendered as `{"error": {"code", "message", "request_id", "details?"}}`. Internal exception text is never returned, and validation errors drop input values.

Both middlewares are pure ASGI, so streaming responses (AI chat, P11) are not buffered.

## Health model

- `GET /health`: liveness, with no I/O.
- `GET /ready`: checks **PostgreSQL** (also reports the schema revision) and **Redis**, both critical, plus **Qdrant** and the **worker heartbeat**, both optional.
  - `ready`: all checks pass (200).
  - `degraded`: an optional dependency is down (200). File management works; AI and processing pause.
  - `not_ready`: a critical dependency is down (503).
- Failure details expose only exception class names or messages we wrote ourselves, never driver errors, which can contain hostnames or credentials.

## Configuration

Typed `Settings` (`saige_api.core.config`). Production refuses to start without `JWT_SECRET` (≥32 chars) and `TOKEN_ENCRYPTION_KEY`, and rejects wildcard CORS. `.env` is for local development only. See [`.env.example`](../../.env.example).

## Contracts

- `docs/api/openapi.json` is generated from FastAPI (`uv run saige-export-openapi`).
- `packages/api-client/src/schema.gen.ts` is generated from it (`npm run codegen`).
- `packages/types/src/enums.gen.ts` is generated from the Python enums (`uv run python scripts/generate_ts_enums.py`).
- CI fails if any of these is stale.

## Roadmap

Phases follow the master plan: P2 database ✓ · P3 auth ✓ · P4 Google Drive ✓ · P5 web file management · P6 mobile · P7 document processing · P8 search · P9 Qdrant · P10 RAG · P11 chat · P12 agent · P13 sync · P14 security hardening · P15 testing · P16 deployment.
