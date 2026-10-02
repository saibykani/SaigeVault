# ADR-0011: Content-based upload validation and sandboxed content serving

**Status:** Accepted · **Date:** 2026-10-02

## Context

Uploads are the main way untrusted bytes enter the system, and the same bytes are later served back to the browser for preview. Filenames and `Content-Type` headers are attacker-controlled. Serving an uploaded HTML or SVG file from our origin would hand any script inside it a vault session.

## Decision

**Upload validation** (`files/validation.py`), before anything reaches storage:

- **Allow-list by extension:** PDF, DOC/DOCX, XLS/XLSX/CSV, PPT/PPTX, TXT/MD/JSON/XML, PNG/JPG/WEBP/GIF and ZIP. HTML, SVG and executables are not accepted.
- **Content detection:** magic bytes (or container structure for Office Open XML) must match the extension. A renamed executable is rejected (`415 content_mismatch`). The stored MIME type is always the detected one.
- **Text formats:** must be UTF-8 and contain no NUL bytes.
- **ZIP / OOXML:** inspected without extraction. Limits are ≤ 10,000 entries, ≤ 2 GiB total uncompressed, and a per-entry compression ratio ≤ 200 (zip-bomb guard).
- **Size:** `MAX_UPLOAD_BYTES` (default 100 MB) is enforced from `Content-Length` before the body is read, and again on the spooled file.
- **Filenames:** basename only, NFC-normalised, control and reserved characters replaced, Windows device names neutralised, ≤ 255 characters. Renames keep the validated extension.
- **Integrity:** the SHA-256 checksum is recorded per file and version.
- Uploads are rate-limited per user.

**Content serving** (`GET /files/{id}/content`):

- Streamed from the storage provider. Storage errors surface before any headers are sent.
- `Content-Security-Policy: sandbox; default-src 'none'`, `X-Content-Type-Options: nosniff` and `Cache-Control: private, no-store`. The global middleware never weakens a route's stricter CSP.
- Inline display is limited to PDF and raster images. Text formats are always served as `text/plain`, so Markdown/JSON/XML are never interpreted. Everything else is `attachment`.
- `Content-Disposition` uses an RFC 5987 `filename*` for Unicode names.
- The web client renders PDFs itself with pdf.js from the fetched bytes (no iframe, no third-party viewer), and shows text in a `<pre>` as plain text.

## Consequences

- Legitimate but unusual files (non-UTF-8 text, encrypted Office files) may be rejected with a clear message.
- Legacy OLE2 formats (DOC/XLS/PPT) share one signature, so the extension decides between them.
- Every request also checks that the file belongs to the signed-in user, as in all phases (ADR-0005).
