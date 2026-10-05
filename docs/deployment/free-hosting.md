# Free hosting (Vercel + Render + MongoDB Atlas + Cloudflare R2)

| Piece | Service (free tier) | Holds |
| --- | --- | --- |
| Web app | Vercel | Pages; proxies `/api/*` to the API |
| API | Render (Docker) | Saige backend |
| Database | MongoDB Atlas (M0) | Users, sessions, file details (name, type, size, R2 key, dates), folders, tags, collections, audit log |
| Files | **MongoDB (default, nothing to set up)**, or any S3-compatible storage (Backblaze B2, Cloudflare R2…) | File content, keyed `documents/`, `images/`, `certificates/`, `resumes/`, `other/` |
| Redis (optional) | Upstash | Rate limits and sign-in state. Without it these are kept in-process, which is fine for one instance |

## 1. MongoDB Atlas

1. In **Database → Connect → Drivers**, copy the `mongodb+srv://…` string.
2. Add the database name after `.net/`, for example `…mongodb.net/saige_vault?appName=…`.
3. If your password contains `@`, `:`, `/`, `?` or `#`, write it percent-encoded. For example, `@` becomes `%40`.
4. In **Network Access**, add `0.0.0.0/0`. Render's free tier has no fixed IP address.

Saige creates its indexes automatically when it starts.

## 2. File storage (optional)

With no `R2_*` settings, files are stored in MongoDB (GridFS) — nothing to set up, but the Atlas free tier is 512 MB in total. For more space, use any S3-compatible service: set `R2_ENDPOINT` (e.g. `https://s3.us-east-005.backblazeb2.com` for Backblaze B2, 10 GB free, no card), `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` and `R2_BUCKET`. Cloudflare R2 steps:

1. In the Cloudflare dashboard, open **R2 Object Storage** and create a bucket named `saige-vault`. Keep it private, with no public access.
2. Click **Manage API tokens → Create API token**. Choose **Object Read & Write**, limited to that bucket.
3. Note these three values:
   - the **Access Key ID**;
   - the **Secret Access Key**;
   - your **Account ID**, shown on the R2 overview page.

R2 requires a payment method on file even for the free tier. 10 GB of storage and downloads (egress) are free.

## 3. Render (API)

Create a **New → Web Service** from this repository:

- **Runtime:** Docker
- **Dockerfile path:** `./infrastructure/docker/backend.Dockerfile`
- **Health check path:** `/health`

Then set these environment variables:

| Key | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `MONGODB_URI` | the Atlas string from step 1 |
| `R2_ACCOUNT_ID` | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | from the R2 API token |
| `R2_SECRET_ACCESS_KEY` | from the R2 API token |
| `R2_BUCKET` | `saige-vault` |
| `JWT_SECRET` | 48+ random characters |
| `TOKEN_ENCRYPTION_KEY` | `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth client (sign-in only) |
| `GOOGLE_REDIRECT_URI` | `https://saigevault.vercel.app/api/v1/auth/google/callback` |
| `WEB_PUBLIC_URL` / `CORS_ALLOWED_ORIGINS` | `https://saigevault.vercel.app` |

Remove `DATABASE_URL`; it's no longer used.

Check that `https://<render-url>/ready` lists `database` and `storage` as `ok`.

## 4. Vercel (web)

1. Set **Root Directory** to `apps/web`.
2. Set `API_PROXY_TARGET` to your Render URL.
3. Redeploy.

## Good to know

- **Cold starts:** Render's free tier sleeps after 15 minutes idle. The first visit after that takes about 30–60 seconds.
- **Secrets** live only in the Render and Vercel dashboards and your local `.env`, never in git. If one is shared, rotate it.
- **Google sign-in** only asks for your name and email. Saige no longer uses Google Drive.
