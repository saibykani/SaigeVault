# Test strategy

## Layers

| Layer | Tooling | Location | Runs in CI |
| --- | --- | --- | --- |
| Python unit | pytest, pytest-asyncio, httpx ASGI transport | `services/*/tests` | ✓ |
| Schema security | pytest over SQLAlchemy metadata | `tests/security` | ✓ |
| Integration (real PostgreSQL, real migrations) | pytest + testcontainers / CI service | `tests/integration` | ✓ |
| TypeScript unit | Vitest | `packages/*/src/*.test.ts` | ✓ |
| Web components | Vitest + Testing Library (jsdom) | `apps/web/src/**/*.test.tsx` | ✓ |
| Web end-to-end | Playwright (desktop Chrome + Pixel 7) | `apps/web/e2e` | ✓ |
| iOS unit / UI | XCTest / XCUITest | `apps/ios/SaigeVault*Tests` | ✓ (macOS runner) |
| Android | JUnit / instrumentation | `apps/android/app/src/test`, `androidTest` | when the shell lands |
| RAG evaluation | precision/recall, MRR, NDCG, faithfulness, citation correctness | `tests/rag` | P15 |
| Contract drift | OpenAPI, TS client and TS enums regenerated and diffed | CI | ✓ |

## What the foundation tests prove

- **Health:** liveness needs no dependencies; readiness maps critical vs optional failures correctly; slow checks time out; driver error messages never leak.
- **HTTP security:** security headers, request-ID generation and sanitisation (header-injection attempt), error envelope, CORS allow-list, docs disabled and HSTS enabled in production, no secrets in `/system/info`.
- **Configuration:** safe defaults, production secret requirements, async driver enforcement, secrets hidden from `repr`.
- **Logging:** redaction of tokens, passwords, document and OCR content, nested headers and bearer tokens.
- **Tenant isolation:** every tenant table has an indexed non-null `user_id`, and every FK between tenant tables includes `user_id`. Against real PostgreSQL, cross-tenant references are rejected, `SET NULL` never clears `user_id`, email uniqueness is case-insensitive, and enum CHECKs reject unknown values.
- **AI policy:** full policy × locality matrix.
- **Worker:** backoff growth and cap, jitter bounds, retry limits, invalid policies rejected.
- **Web:** readiness copy, feature registry, command-palette filtering and navigation, keyboard-shortcut guards, every page renders, security headers, 404 page, theme switching, no network request when an unavailable upload is triggered, mobile navigation.

## Rules

- Integration tests refuse a `TEST_DATABASE_URL` whose database name does not contain `test` (the fixture drops the schema).
- Tests never call real AI providers or Google APIs. Provider adapters are tested against recorded or fake transports.
- A skipped integration test is reported as skipped, never as passed.

## Running

```bash
uv run pytest                    # all Python tests (Docker needed for integration)
npm test                         # all TS unit/component tests
npm run e2e                      # Playwright (builds and starts the web app)
cd apps/ios && make test         # macOS only
```
