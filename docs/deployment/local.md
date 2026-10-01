# Local development

## Prerequisites

- Docker Desktop (Compose v2)
- Python 3.12 and [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- Node.js 24 and npm 11
- For iOS: macOS with Xcode 16+ ([mobile/ios.md](../mobile/ios.md))
- For Android: JDK 17+ and the Android SDK ([mobile/android.md](../mobile/android.md))

## Run everything in Docker

```bash
cp .env.example .env          # set POSTGRES_PASSWORD at minimum
docker compose up -d --build
```

| Service | URL |
| --- | --- |
| Web | http://localhost:3000 |
| API | http://localhost:8000 (interactive docs at `/docs`) |
| Readiness | http://localhost:8000/ready |
| Qdrant | http://localhost:6333/dashboard |

The `migrate` service applies Alembic migrations before `api` and `worker` start.

**Port conflicts:** every published port binds to `127.0.0.1` and can be moved, e.g. `WEB_PORT=3001 API_PORT=8001 docker compose up -d`. If you change the web port, also add its origin to `CORS_ALLOWED_ORIGINS`.

## Run services from source (faster iteration)

```bash
docker compose up -d postgres redis qdrant      # infrastructure only
uv sync                                         # Python workspace
uv run alembic -c services/api/alembic.ini upgrade head
uv run uvicorn saige_api.main:create_app --factory --reload --port 8000
uv run saq saige_worker.main.settings           # separate terminal

npm install
npm run dev:web                                 # http://localhost:3000
```

## Quality gates (run before every commit)

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy services/api/src services/worker/src services/ai/src
uv run pytest                                   # integration tests need Docker or TEST_DATABASE_URL
npm run lint && npm run typecheck && npm test && npm run build:web
npm run e2e                                     # Playwright
```

## Regenerating contracts

After changing API schemas or enums:

```bash
uv run saige-export-openapi                     # docs/api/openapi.json
npm run codegen                                 # packages/api-client
uv run python scripts/generate_ts_enums.py      # packages/types
```
