# API

- **Specification:** [`openapi.json`](openapi.json), generated from the FastAPI app (`uv run saige-export-openapi`). CI fails if it is stale.
- **Interactive docs:** `http://localhost:8000/docs` (disabled when `APP_ENV=production`).
- **Base path:** `/api/v1` for product endpoints. Probes live at the root.

## Conventions

- JSON only, UTF-8, `snake_case` fields.
- Every response carries `X-Request-ID`. Clients may send their own (8–128 chars of `[A-Za-z0-9._-]`), otherwise one is generated.
- Errors always use the same envelope:

```json
{ "error": { "code": "not_found", "message": "File not found", "request_id": "4f1c…", "details": null } }
```

| Status | `code` | Meaning |
| --- | --- | --- |
| 400 | `bad_request` | Malformed request |
| 401 | `unauthorized` | Missing or invalid credentials |
| 403 | `forbidden` | Authenticated but not allowed |
| 404 | `not_found` | Missing, **or owned by another user** (existence is never disclosed) |
| 409 | `conflict` | State conflict |
| 422 | `validation_error` | Body or params failed validation (`details` lists locations, without input values) |
| 429 | `rate_limited` | Too many requests |
| 500 | `internal_error` | Unexpected error; reference `request_id` |

## Endpoints (built)

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Liveness, no I/O |
| GET | `/ready` | Dependency readiness: `ready` / `degraded` (200), `not_ready` (503) |
| GET | `/api/v1/system/info` | Version, environment, AI processing policy, whether Google OAuth is configured. No secrets |

## Planned resource groups

`/api/v1/auth` (P3) · `/users` · `/storage` (P4) · `/files`, `/folders`, `/collections`, `/tags` (P5) · `/documents` (P7) · `/search` (P8) · `/ai`, `/chat` (P10–P11) · `/agents` (P12) · `/sync` (P13) · `/settings`.

## Clients

- TypeScript: `@saige/api-client` (`openapi-fetch` with generated types).
- iOS: `APIClient.swift` with `Codable` models mirroring the spec.
- Android: planned, with Kotlin `@Serializable` models.
