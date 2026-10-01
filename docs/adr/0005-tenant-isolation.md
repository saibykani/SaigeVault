# ADR-0005: Tenant isolation enforced in the database with composite foreign keys

**Status:** Accepted · **Date:** 2026-10-01

## Context

Even a single-user deployment must be architected as multi-tenant. A bug that lets one user's file be tagged, collected, chunked or retrieved under another user's account would be a severe privacy breach, especially through AI retrieval.

## Decision

Three layers of defence:

1. **Every user-owned table has `user_id NOT NULL`, indexed, referencing `users.id`.** Only `users`, `audit_logs`, `security_events` and `feature_flags` are exempt, and that allow-list is enforced by a test.
2. **Composite foreign keys.** Each parent table has `UNIQUE (id, user_id)`. Children reference `(parent_id, user_id)`, so the database itself rejects a row pointing at another user's resource. Optional references use `ON DELETE SET NULL (column)` (PostgreSQL 15+) so that `user_id` is never cleared.
3. **Application layer:** every query filters by the authenticated `user_id`. A resource owned by someone else returns `404` (not `403`), so existence is never disclosed.

Automated guards:

- `tests/security/test_tenant_isolation_schema.py` fails if a tenant table lacks `user_id`, or if any FK between tenant tables omits `user_id`. It already caught `user_sessions.rotated_from_id` during development.
- `tests/integration/test_schema_constraints.py` proves cross-tenant inserts are rejected by real PostgreSQL.

## Consequences

- Slightly wider foreign keys and one extra unique index per parent table.
- PostgreSQL Row-Level Security can be layered on later (Phase 14) without schema changes.
