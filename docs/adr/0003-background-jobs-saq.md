# ADR-0003: Background jobs with SAQ on Redis, durable state in PostgreSQL

**Status:** Accepted · **Date:** 2026-10-01

## Context

Document processing (extraction, OCR, embeddings) is slow and must never block uploads. Jobs need retries, exponential backoff, dead-lettering, idempotency and progress tracking.

Options considered:

- **arq** — rejected: its latest release pins `redis<6`, so it is incompatible with current redis-py and effectively unmaintained.
- **Celery** — mature but synchronous-first and heavy for an asyncio codebase.
- **SAQ** — asyncio-native, actively maintained, Redis-backed, with retries, timeouts, cron, heartbeats and job status.

## Decision

- **Queue transport: SAQ on Redis** (Redis runs with AOF persistence and `noeviction`).
- **Durable truth: `document_processing_jobs` in PostgreSQL.** It tracks status, attempts, progress, the current stage, sanitized errors and a unique `idempotency_key`. Redis can be lost without losing job history.
- **Retry policy:** capped exponential backoff with full jitter (`saige_worker.retry.RetryPolicy`). After `max_attempts` a job becomes `dead_lettered`, so it can be inspected instead of retrying forever.
- The worker publishes a **heartbeat** to Redis, which the API's `/ready` reports on.

## Consequences

- `redis-py` is constrained to `<8` by SAQ.
- Job handlers must be idempotent: the same `idempotency_key` must be safe to process twice.
