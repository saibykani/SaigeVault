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
| GET | `/api/v1/system/info` | Version, environment, AI processing policy, whether Google OAuth and dev sign-in are enabled. No secrets |
| GET | `/api/v1/auth/google/login?next=` | Starts Google sign-in (302 to Google). Rate-limited |
| GET | `/api/v1/auth/google/callback` | OAuth callback: verifies state, PKCE and ID token, then sets session cookies and redirects to the web app |
| POST | `/api/v1/auth/dev-login` | Development-only email sign-in. `404` unless `DEV_LOGIN_ENABLED` (never in production) |
| POST | `/api/v1/auth/refresh` | Rotates the refresh token. Cookie mode needs `X-CSRF-Token`; body mode (`refresh_token`) returns a token pair for API clients |
| POST | `/api/v1/auth/logout` | Ends this session and clears cookies (`204`) |
| GET | `/api/v1/auth/session` | Current user and session (`401` when signed out) |
| GET | `/api/v1/auth/sessions` | Active sessions for this user |
| DELETE | `/api/v1/auth/sessions/{id}` | Revokes one of your sessions (`404` if not yours) |

| GET | `/api/v1/storage/connections` | Your storage connections (status, account, scopes; never credentials) |
| GET | `/api/v1/storage/google-drive/connect?next=` | Starts the Drive consent flow (302 to Google). Requires sign-in; `503` if Drive isn't configured |
| POST | `/api/v1/storage/connections/{id}/disconnect` | Revokes access at Google and deletes stored credentials; files stay in Drive |
| GET | `/api/v1/storage/connections/{id}/quota` | Google account storage usage. `409 storage_reauth_required` if access was revoked |

| GET | `/api/v1/files` | List files with `folder_id`, `q` (name), `type`, `document_type`, `starred`, `trashed`, `tag`, `collection_id`, `all_folders`, `sort`, `order`, `limit`, `offset`. Returns subfolders + breadcrumbs when browsing |
| POST | `/api/v1/files` | Upload (`multipart/form-data`: `file`, optional `folder_id`). `413 file_too_large`, `415 unsupported_type` / `content_mismatch`, `409 storage_not_connected` |
| GET | `/api/v1/files/stats` | Counts and bytes for the dashboard |
| GET / PATCH | `/api/v1/files/{id}` | Get; rename / move (`folder_id` or `move_to_root`) / star / reclassify (`document_type`, recorded as a user override) |
| GET | `/api/v1/files/{id}/content?inline=` | Stream content (sandboxed; see ADR-0011) |
| DELETE | `/api/v1/files/{id}` | Move to trash (storage trash too) |
| POST | `/api/v1/files/{id}/restore` | Restore from trash (back to root if its folder is gone) |
| DELETE | `/api/v1/files/{id}/permanent` | Delete forever, including from storage. Only for trashed files (`409` otherwise) |
| POST | `/api/v1/files/bulk` | `trash` / `restore` / `star` / `unstar` / `move` for up to 500 files. Returns `succeeded` and `failed` IDs |
| PUT | `/api/v1/files/{id}/tags` | Replace the file's manual tags (normalised, `#` optional) |
| POST / PATCH / DELETE | `/api/v1/folders[/{id}]` | Create, rename/move (no cycles), delete (empty folders only) |
| GET / DELETE | `/api/v1/tags[/{id}]` | List or delete your tags |
| GET / POST | `/api/v1/collections` | List (with file counts) or create (names unique, case-insensitive) |
| GET / PATCH / DELETE | `/api/v1/collections/{id}` | Detail with files, update, delete (files are kept) |
| POST / DELETE | `/api/v1/collections/{id}/files[/{file_id}]` | Add files (foreign IDs are ignored) or remove one |

Storage errors use the standard envelope with codes `storage_not_found` (404), `storage_reauth_required` (409), `storage_permission_denied` (403), `storage_quota_exceeded` (507) and `storage_unavailable` (503).

**Authentication:** send `Authorization: Bearer <access token>`, or use the browser session cookies. Cookie-authenticated `POST`/`PUT`/`PATCH`/`DELETE` require `X-CSRF-Token` equal to the `saige_csrf` cookie.

## Planned resource groups

`/users` · `/documents` (P7) · `/search` (P8) · `/ai`, `/chat` (P10–P11) · `/agents` (P12) · `/sync` (P13) · `/settings`.

## Clients

- TypeScript: `@saige/api-client` (`openapi-fetch` with generated types).
- iOS: `APIClient.swift` with `Codable` models mirroring the spec.
- Android: planned, with Kotlin `@Serializable` models.
