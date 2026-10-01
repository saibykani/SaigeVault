# ADR-0010: `drive.file` scope, separate consent, and AES-GCM token encryption

**Status:** Accepted · **Date:** 2026-10-02

## Context

Saige stores the user's most sensitive documents in their Google Drive. Broad Drive access (`drive`) would expose every file in the account to Saige and to anyone who compromises Saige. Long-lived refresh tokens are effectively passwords to the user's Drive.

## Decision

- **Scope `https://www.googleapis.com/auth/drive.file`** (configurable via `GOOGLE_DRIVE_SCOPE`). Saige can only access files it created, which live in its own **Saige Vault** folder. That folder is found by a private `appProperties` marker, never by name, so a user folder with the same name is never confused for it. The rest of the user's Drive stays invisible to Saige.
- **Separate, explicit consent.** Sign-in asks only for `openid email profile`. Connecting Drive is a second Google consent (`access_type=offline`, `prompt=consent`, PKCE, nonce) bound to the signed-in user who started it. If a different account completes it, the connection is rejected. The callback checks that the Drive scope was actually granted, since users can untick it on Google's screen.
- **Token custody:**
  - Access and refresh tokens are encrypted with **AES-256-GCM** (`TOKEN_ENCRYPTION_KEY`, 32-byte url-safe base64).
  - Ciphertext layout: `version | nonce | ciphertext+tag`. `token_key_version` supports key rotation.
  - Associated data is `storage_connection:<id>:<field>`, so a ciphertext copied to another row or column fails to decrypt.
  - Tokens are decrypted only in memory, only on the server, and never returned by any API.
- **Refresh** happens under a row lock (`SELECT … FOR UPDATE`) in its own transaction. `invalid_grant` (the user revoked access) marks the connection `needs_reauth`, and that status is committed before the error is surfaced.
- **Disconnect** revokes the refresh token at Google (best effort, reported to the user), wipes the ciphertexts, and keeps the connection row for audit. Files stay in Drive.
- **Drive client:** a 401 triggers one token refresh. 429, 5xx and Drive rate-limit 403s are retried with capped exponential backoff and jitter. Item IDs are validated (`[A-Za-z0-9_-]`), and no caller-supplied text ever enters a Drive `q` query. Uploads ≤ 5 MiB use one multipart request; larger ones use resumable 8 MiB chunks.

## Consequences

- With `drive.file`, files a user adds to the Saige Vault folder *directly in the Drive UI* are not visible to Saige. Uploads must go through Saige. Switching to full `drive` scope is a deliberate, documented operator choice (it also needs Google's restricted-scope verification for public apps).
- Losing `TOKEN_ENCRYPTION_KEY` means every connection must be reconnected. Files are unaffected.
- Drive is unavailable (and the UI says so) until both Google OAuth credentials and `TOKEN_ENCRYPTION_KEY` are configured.
