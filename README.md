# Saige Vault

**A private, AI-powered vault for your personal documents.** Certificates, payslips, offer letters, IDs, resumes and notes, all organised, searchable and answerable from one place, while the originals stay in your own Google Drive.

Clients: **Saige Vault Web** · **Saige Vault iOS** · **Saige Vault Android**. All three share a single backend, auth system, database, AI layer and storage.

> **Status: Phases 0–5 complete.** You can upload, organise, preview, tag and collect your documents. Sign-in, Google Drive connection, file management and previews are built and tested. File management, document processing, search and AI arrive phase by phase. The UI says plainly what isn't built yet and never fakes it.

## Architecture

```text
   Web (Next.js)     iOS (SwiftUI)     Android (Compose)
          \               |                 /
           \_____ REST /api/v1 (HTTPS) ____/
                          |
                 API (FastAPI, Python)
         /         |           |          \
   PostgreSQL    Redis      Qdrant     Google Drive
   metadata    queue      vectors      original files
               |
         Worker (SAQ) → AI layer (LLM · embeddings · reranker · OCR providers)
```

Read more: [system](docs/architecture/system.md) · [storage](docs/architecture/storage.md) · [RAG](docs/architecture/rag.md) · [agent](docs/architecture/agent.md) · [security](docs/security/security-model.md) · [ADRs](docs/adr/README.md)

## Quick start

```bash
cp .env.example .env            # set POSTGRES_PASSWORD
docker compose up -d --build
```

- Web: http://localhost:3000
- API: http://localhost:8000/docs
- Readiness: http://localhost:8000/ready

Port already in use? Run `WEB_PORT=3001 API_PORT=8001 docker compose up -d` (see [local development](docs/deployment/local.md)).

**iPhone:** see [docs/mobile/ios.md](docs/mobile/ios.md). You need a Mac with Xcode; a free Apple ID is enough for a personal install.

## Repository layout

```text
apps/web        Next.js web client
apps/ios        SwiftUI app (XcodeGen project spec)
apps/android    Jetpack Compose app
services/api    FastAPI service + SQLAlchemy models
services/worker Background worker (SAQ)
services/ai     Provider-independent AI interfaces + privacy policy gate
packages/       Shared TypeScript: generated API client, enums, utilities, tsconfig
database/       Alembic migrations, seeds
infrastructure/ Dockerfiles, reverse proxy, deployment
docs/           Architecture, ADRs, API, security, deployment, mobile, testing
tests/          Cross-service integration, security, e2e and RAG suites
```

## Development

```bash
uv sync && npm install
uv run pytest                   # Python unit + integration (Docker)
npm test && npm run e2e         # TypeScript unit + Playwright
```

Every change must pass lint, type checks, tests and builds. CI runs them all, plus contract-drift checks, iOS tests on macOS, secret scanning and dependency audits.

## Privacy principles

- Your files stay in your storage. Saige stores references and metadata.
- AI processing is **disabled by default**. The operator chooses `local_only` or `third_party_allowed`.
- Documents are never used to train models, and instructions inside documents are treated as data, never commands.
- AI answers cite their sources and distinguish facts from inference. If the answer isn't in your documents, Saige says so.

## License

Proprietary. All rights reserved (see [LICENSE](LICENSE)).
