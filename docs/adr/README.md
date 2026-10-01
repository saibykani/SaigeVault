# Architecture Decision Records

Each ADR records one significant decision: its context, the decision, and its consequences. ADRs are immutable once accepted — supersede them with a new ADR instead of editing.

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-monorepo-and-stack.md) | Monorepo and technology stack | Accepted |
| [0002](0002-storage-provider-abstraction.md) | Google Drive as primary storage behind a StorageProvider abstraction | Accepted |
| [0003](0003-background-jobs-saq.md) | Background jobs with SAQ on Redis, durable state in PostgreSQL | Accepted |
| [0004](0004-enums-as-check-constraints.md) | Enums stored as VARCHAR + CHECK constraints | Accepted |
| [0005](0005-tenant-isolation.md) | Tenant isolation enforced in the database with composite foreign keys | Accepted |
| [0006](0006-ai-provider-abstraction-and-policy.md) | Provider-independent AI layer gated by an AI processing policy | Accepted |
| [0007](0007-search-and-vector-index.md) | PostgreSQL full-text + Qdrant; Qdrant is a derived index | Accepted |
| [0008](0008-native-mobile-clients.md) | Native mobile clients (SwiftUI, Jetpack Compose) with no business logic | Accepted |
| [0009](0009-sessions-and-same-origin-proxy.md) | Rotating refresh-token sessions behind a same-origin proxy | Accepted |
