# ADR-0002: Google Drive as primary storage behind a StorageProvider abstraction

**Status:** Accepted · **Date:** 2026-10-01

## Context

The user's documents are highly sensitive and must remain under their control. Storing binaries in PostgreSQL bloats backups and couples the app to its own database. The user already trusts Google Drive.

## Decision

- **Original files live in the user's Google Drive.** The storage provider is the source of truth for file content and revisions.
- **PostgreSQL stores references and metadata only:** `storage_file_id`, MIME type (detected server-side), size, checksum, processing state, AI metadata.
- All storage access goes through a `StorageProvider` interface (Phase 4) with `GoogleDriveStorageProvider` as the first implementation. Future providers (OneDrive, Dropbox, S3, Azure Blob) implement the same interface.
- OAuth is handled entirely by the backend. Refresh/access tokens are encrypted at rest (`storage_connections.encrypted_*`, with `token_key_version` for key rotation) and are never sent to any client.

## Consequences

- Drive API quotas and latency apply to downloads and processing; the worker must handle rate limits with backoff.
- Changes made directly in Drive must be detected via the Drive Changes API (`changes_page_token`, Phase 13).
- Users are never locked in: their files stay in their own Drive, and metadata is exportable.
