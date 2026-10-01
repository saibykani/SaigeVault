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

## Signing in

**Quickest (local only):** set `DEV_LOGIN_ENABLED=true` (already set in `.env.example`) and sign in with any email on the login page. It is refused when `APP_ENV=production`.

**Google sign-in (free):**

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Open **APIs & Services → OAuth consent screen**. Choose **External**, fill in the app name and your email, and add yourself under **Test users**.
3. Open **APIs & Services → Credentials → Create credentials → OAuth client ID**, choose **Web application**, and add this **Authorized redirect URI**:
   `http://localhost:3000/api/v1/auth/google/callback`
   (Use your web origin and port, e.g. `:3001` if you changed `WEB_PORT`.)
4. Put the values in `.env`:
   ```text
   GOOGLE_CLIENT_ID=…apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=…
   GOOGLE_REDIRECT_URI=http://localhost:3000/api/v1/auth/google/callback
   WEB_PUBLIC_URL=http://localhost:3000
   JWT_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(48))">
   ```
5. Run `docker compose up -d --build`. **Continue with Google** is now enabled.

Without `JWT_SECRET` the API uses a temporary key, and everyone is signed out whenever it restarts.

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
