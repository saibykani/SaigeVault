# ADR-0013: MongoDB for metadata, Cloudflare R2 for file content

**Status:** Accepted · **Date:** 2026-10-05 · **Supersedes:** ADR-0004, ADR-0005 (database parts), ADR-0010

## Context

The owner wants simple, free hosting. They chose MongoDB Atlas for data and Cloudflare R2 (10 GB free, no egress fees) for files, replacing PostgreSQL and Google Drive.

## Decision

**MongoDB:**
- Collections: `users` (with an embedded `password` credential), `oauth_accounts`, `sessions`, `files`, `folders`, `tags`, `collections`, `audit_logs` and `security_events`.
- Ids are UUIDs (BSON subtype 4). Dates are UTC-aware.
- Indexes are created at startup (`db.ensure_indexes`). There are no migrations.
- **Tenant isolation:** every query on user data filters by `user_id` (`VaultService._mine`). Cross-tenant references (collections → files, files → tags) are resolved only within the same user's documents.
- **Atomic operations replace row locks:**
  - Refresh-token rotation uses `find_one_and_update` on an unrevoked token.
  - TOTP step advancement and recovery-code use are conditional updates.

**Cloudflare R2:**
- Accessed through its S3-compatible API (boto3 running in worker threads). The bucket is private.
- Objects are keyed `{category}/{user_id}/{file_id}.{ext}`. The category is `documents`, `images`, `certificates`, `resumes` or `other`. It is chosen at upload, or derived from the file type.
- Content is uploaded only after validation (ADR-0011), and is always served through the API with the sandboxed headers.
- Trash is a database flag. Permanent delete removes the object.
- Folders, tags and collections exist only in MongoDB.
- Without R2 settings, uploads return `503 storage_not_configured`. Development can set `MEMORY_STORAGE=true`.

**Google** is used for sign-in only (`openid email`).

## Consequences

- Fewer moving parts and no migrations. Integrity rules that PostgreSQL enforced (composite foreign keys, CHECK constraints) are now enforced in application code and covered by tests.
- Google Drive linking and the Picker were removed.
