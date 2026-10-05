# Free hosting (Vercel + Render + Neon + Upstash)

This puts Saige Vault online for free, so `https://saigevault.vercel.app` and your phone can sign in. It takes about 20 minutes, done once.

| Piece | Service (free tier) | Holds |
| --- | --- | --- |
| Web app | Vercel | Pages; proxies `/api/*` to the API |
| API | Render (Docker) | Saige backend; runs migrations on deploy |
| Database | Neon (PostgreSQL) | Metadata, sessions, audit |
| Redis (optional) | Upstash | Rate limits, sign-in state. Without it these are kept in-process, which is fine for one free instance |
| Files | Your Google Drive | Original documents |

> **Why PostgreSQL, not MongoDB?** Saige's schema, migrations and tenant isolation (ADR-0005) are built on PostgreSQL features: composite foreign keys, CHECK constraints and transactions. MongoDB isn't a drop-in replacement.

## 1. Database — Neon

1. Sign up at [neon.tech](https://neon.tech) and create a project (pick a region near you).
2. On the dashboard, click **Connect** and copy the connection string (`postgresql://…neon.tech/neondb?sslmode=require…`).

Paste it as-is later. Saige converts it for its driver automatically.

## 2. Redis — Upstash (optional, skip if you like)

Skip this step to start. Without `REDIS_URL`, the API keeps sign-in state and rate limits in memory, which is correct for a single instance. Add Redis later if you run more than one API instance.


1. Sign up at [upstash.com](https://upstash.com) and create a **Redis** database.
2. Copy the **`rediss://default:…@….upstash.io:6379`** URL. Note the double `s`, which means TLS.

## 3. Google Cloud (OAuth client)

In your OAuth client (APIs & Services → Credentials), add **both** Authorized redirect URIs:

```text
https://saigevault.vercel.app/api/v1/auth/google/callback
http://localhost:3001/api/v1/auth/google/callback
```

Also:
- **OAuth consent screen → Test users:** add your Google address.
- **APIs & Services → Library:** enable **Google Drive API**.
- **Data access / Scopes:** add `…/auth/drive.file`.

## 4. API — Render (plain Web Service, no Blueprint needed)

1. Go to [dashboard.render.com](https://dashboard.render.com), click **New → Web Service**, and connect GitHub. Select `saibykani/SaigeVault`.
2. Fill in the service settings:
   - **Language/Runtime:** Docker
   - **Branch:** `main`
   - **Region:** Singapore
   - **Dockerfile Path:** `./infrastructure/docker/backend.Dockerfile`
   - **Docker Build Context:** `.`
   - **Instance type:** Free
   - Leave **Start/Docker Command** empty. The image runs migrations and binds to `$PORT` on its own.
3. Under **Advanced → Health Check Path**, enter `/health`.
4. Under **Environment Variables**, add:

   | Key | Value |
   | --- | --- |
   | `APP_ENV` | `production` |
   | `DATABASE_URL` | Neon **direct** URL (host without `-pooler`) |
   | `GOOGLE_CLIENT_ID` | your OAuth client ID |
   | `GOOGLE_CLIENT_SECRET` | your OAuth client secret |
   | `JWT_SECRET` | click **Generate** (or any random string of 48+ characters) |
   | `TOKEN_ENCRYPTION_KEY` | 32 random bytes, base64. Click **Generate**, or run `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"` |
   | `WEB_PUBLIC_URL` | `https://saigevault.vercel.app` |
   | `GOOGLE_REDIRECT_URI` | `https://saigevault.vercel.app/api/v1/auth/google/callback` |
   | `CORS_ALLOWED_ORIGINS` | `https://saigevault.vercel.app` |

5. Click **Deploy Web Service**. The logs should show `Running upgrade` lines, then `Application startup complete`. Copy the URL (e.g. `https://saige-vault-api.onrender.com`) and check that `/health` returns `{"status":"ok"…}`.

Prefer automation? **New → Blueprint** with this repository does the same thing from [`render.yaml`](../../render.yaml).

## 5. Web — Vercel

1. Go to **Project → Settings → Build and Deployment** and set **Root Directory** to `apps/web`. The Framework should then show Next.js.
2. Under **Settings → Environment Variables**, add `API_PROXY_TARGET` = your Render URL (no trailing slash), for all environments.
3. Go to **Deployments → ⋯ → Redeploy**. Proxy rewrites are fixed at build time, so a redeploy is required.

Open `https://saigevault.vercel.app` and click **Continue with Google**.

## Good to know

- **Cold starts:** Render's free tier sleeps after 15 minutes idle. The first visit after that takes about 30–60 seconds, and the login page shows "Waking up the server…" meanwhile. To avoid it, a free monitor (e.g. UptimeRobot) can ping `<render-url>/health` every 10 minutes. One always-on service fits within Render's free monthly hours.
- **AI and the background worker** aren't deployed yet, so `/ready` reports `degraded`. That's expected until document processing (Phase 7).
- **Costs:** everything above is free tier. Nothing here creates paid resources. Check each provider's current limits, which change over time.
- **Staying connected to Drive:** the connection is stored encrypted and lasts until you disconnect it. While the Google app is in **Testing**, Google itself expires that access after 7 days. Publish the app (**Google Auth Platform → Audience → Publish app**) to stop this. `drive.file` is a non-sensitive scope, so publishing needs no Google review.
- **Password sign-in** works out of the box. Two-step verification needs `TOKEN_ENCRYPTION_KEY`, which you already set.
- **Secrets:** they live only in the Render and Vercel dashboards and your local `.env`, never in git. If a secret is ever shared, rotate it: reset the Google client secret, or reset the Neon/Upstash password and update Render.
