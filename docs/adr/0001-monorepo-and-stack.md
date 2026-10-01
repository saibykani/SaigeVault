# ADR-0001: Monorepo and technology stack

**Status:** Accepted · **Date:** 2026-10-01

## Context

Saige Vault has a backend API, a background worker, an AI layer, a web client and two native mobile clients. The API contract must stay synchronized across all clients, and one developer must be able to change a contract and every consumer in a single commit.

## Decision

- **One monorepo** with `apps/`, `services/`, `packages/`, `database/`, `infrastructure/`, `docs/`, `tests/`.
- **Backend: Python 3.12 + FastAPI**, SQLAlchemy 2 (async) + asyncpg, Alembic, Pydantic v2, structlog. Python has the strongest document-processing, OCR and AI ecosystem (PDF/Office parsers, Tesseract bindings, every LLM SDK), which matters more for this product than raw request throughput.
- **Python workspace managed by uv** (`uv.lock` committed) with three members: `saige-api`, `saige-worker`, `saige-ai`.
- **Web: Next.js 16 + TypeScript + Tailwind CSS 4 + shadcn/ui-style components** (Radix primitives), TanStack Query for server state, Zustand for client UI preferences only.
- **TypeScript workspace managed by npm workspaces**: `@saige/web`, `@saige/api-client`, `@saige/types`, `@saige/shared`, `@saige/config`.
- **Contract synchronization by code generation:**
  - FastAPI → `docs/api/openapi.json` → `openapi-typescript` → `@saige/api-client` types.
  - Python enums → `scripts/generate_ts_enums.py` → `@saige/types`.
  - CI fails if any generated artifact is stale.

## Consequences

- Two package managers (uv, npm), which is idiomatic for each ecosystem and keeps lockfiles authoritative.
- Mobile clients mirror the OpenAPI models by hand today (Swift `Codable`, Kotlin `@Serializable`). Generated Swift/Kotlin clients can be added later from the same spec.
- TypeScript is pinned to 6.0.x: TypeScript 7 (native Go compiler) does not yet expose the compiler API that Next.js relies on.
