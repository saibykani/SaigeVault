# ADR-0004: Enums stored as VARCHAR + CHECK constraints

**Status:** Accepted · **Date:** 2026-10-01

## Context

Many columns are enumerations (processing status, document type, audit action…). Native PostgreSQL `ENUM` types cannot drop values and complicate migrations (`ALTER TYPE … ADD VALUE` cannot run inside a transaction on older versions).

## Decision

Enumerations are `VARCHAR(n)` columns with a named `CHECK (col IN (...))` constraint (`saige_api.db.base.str_enum`). The Python `StrEnum` in `saige_api/models/enums.py` is the single source of truth. TypeScript enums are generated from it.

## Consequences

- Adding or removing a value is a plain constraint swap in a migration.
- Integrity is the same as a native enum.
- Alembic autogenerate emits each enum's CHECK twice. The initial migration was post-processed to keep exactly one constraint per enum. Future migrations touching enums must be reviewed for this.
