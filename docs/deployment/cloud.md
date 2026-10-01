# Cloud deployment

**Status: Planned (P16).** This page documents the target and its constraints now, so earlier phases don't paint us into a corner.

## Target topology

A single small VM running Docker Compose behind a TLS-terminating reverse proxy (Caddy or nginx, `infrastructure/nginx`):

```text
Internet → 443 (TLS) → reverse proxy → web:3000, api:8000
                                    (postgres, redis, qdrant, worker: private network only)
```

## Resource expectations (single user)

| Component | RAM | Notes |
| --- | --- | --- |
| PostgreSQL | 256–512 MB | Grows with chunks and chat history |
| Qdrant | 256 MB–1 GB | ~6 KB per 1536-d vector; 100k chunks ≈ 0.6 GB |
| Redis | 64 MB | Queue only |
| API + worker | 300–600 MB | OCR (Tesseract) spikes CPU during processing |
| Web | 150 MB | |

A 2 vCPU / 4 GB VM is comfortable. 1 GB free-tier VMs work only with swap and without local LLMs.

## Free tier limitations

- Free VM offerings (e.g. Oracle Cloud Always Free, Google Cloud e2-micro) have limited RAM, egress caps and may reclaim idle instances.
- Google Drive storage is the user's own quota (15 GB free).
- **AI API calls cost money.** Embedding a typical document set is cheap, but chat and summarization scale with use. Local models (Ollama) avoid API cost but need much more RAM or a GPU.
- **The application never creates paid resources.** All provisioning is manual and documented.

## Production checklist

- Secrets come from a secret manager or the host's environment, never from a committed file. Set `APP_ENV=production`, `JWT_SECRET` and `TOKEN_ENCRYPTION_KEY`.
- HTTPS only. Set `NEXT_PUBLIC_API_BASE_URL=https://…` (this enables `upgrade-insecure-requests` and HSTS).
- Restrict `CORS_ALLOWED_ORIGINS` to the web origin.
- Use a strong `POSTGRES_PASSWORD`, set `QDRANT_API_KEY`, and never publish database ports.
- Back up per [Backup strategy](#backup-strategy).

## Backup strategy

| Data | Strategy |
| --- | --- |
| Original files | Live in Google Drive (Drive keeps revisions). Optionally export via Google Takeout |
| PostgreSQL | Nightly `pg_dump -Fc`, encrypted (e.g. `age`) and copied off-host; keep 7 daily + 4 weekly; restore-tested monthly |
| Qdrant | Not backed up. It is rebuilt from `document_chunks` by a re-index job (ADR-0007) |
| Redis | Not backed up. Job truth lives in PostgreSQL |

Recovery order: restore PostgreSQL → run migrations → start services → trigger re-indexing for Qdrant.
