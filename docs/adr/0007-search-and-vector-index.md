# ADR-0007: PostgreSQL full-text + Qdrant; Qdrant is a derived index

**Status:** Accepted · **Date:** 2026-10-01

## Context

Search needs exact, full-text, semantic and hybrid modes. A separate search engine (OpenSearch, Meilisearch) would add significant operational weight for a personal deployment.

## Decision

- **Keyword / full-text search: PostgreSQL** (`to_tsvector` GIN index on `document_chunks.content`, plus filename search). Filters are joins on existing tables.
- **Semantic search: Qdrant.** Every Qdrant point carries `user_id` in its payload, and every query filters on it.
- **Hybrid:** reciprocal-rank fusion of both result sets, followed by optional reranking.
- **Qdrant is a derived, rebuildable index.** `document_chunks` (PostgreSQL) holds the text; `embedding_records` maps chunks to Qdrant point IDs. Losing Qdrant means re-embedding, never data loss.

## Consequences

- Backups cover Google Drive (originals) and PostgreSQL. Qdrant is excluded from the backup requirement.
- Changing embedding models is a re-index job keyed on `(chunk_id, provider, model)`.
