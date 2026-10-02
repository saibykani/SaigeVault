# Full-stack browser tests

`apps/web/e2e` holds the Playwright suite that runs in CI against the web app alone.

`apps/web/e2e/full-stack/files-flow.mjs` drives a **real browser against the real API** (real
PostgreSQL + Redis). Google and Google Drive are replaced by in-process fakes
(`tests/e2e/fake_stack.py`), because CI has no Google credentials. It covers:

- signing in and connecting Drive
- uploading a real multi-page PDF, a PNG and a Markdown file, and rejecting a disguised executable
- PDF rendering with pdf.js under the production CSP
- inert text preview
- folders, moving files and breadcrumbs
- renaming (the extension is preserved), tags, stars and collections
- trash, undo and permanent delete with confirmation
- live dashboard metrics

```bash
docker compose up -d postgres redis
docker compose exec postgres createdb -U saige saige_e2e_test
DATABASE_URL=postgresql+asyncpg://saige:change-me-local-only@127.0.0.1:5432/saige_e2e_test \
  uv run alembic -c services/api/alembic.ini upgrade head
uv run python tests/e2e/fake_stack.py --web http://localhost:3101 --port 8010 &
cd apps/web && API_PROXY_TARGET=http://127.0.0.1:8010 npm run build && npx next start --port 3101 &
node apps/web/e2e/full-stack/files-flow.mjs test-results
```

`fake_stack.py` is test tooling only. It refuses to run against a database whose name doesn't contain `test`.
