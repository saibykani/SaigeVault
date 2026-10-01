# syntax=docker/dockerfile:1.7
# Saige Vault web (Next.js standalone output).
# Build context: repository root.

ARG NODE_VERSION=24

FROM node:${NODE_VERSION}-alpine AS deps
WORKDIR /repo
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages/api-client/package.json packages/api-client/package.json
COPY packages/types/package.json packages/types/package.json
COPY packages/shared/package.json packages/shared/package.json
COPY packages/config/package.json packages/config/package.json
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

FROM deps AS builder
# Public, build-time configuration only. Never pass secrets as build args.
# Where Next.js proxies /api/* (baked into the build's rewrite table).
ARG API_PROXY_TARGET=http://api:8000
ENV API_PROXY_TARGET=$API_PROXY_TARGET \
    NEXT_TELEMETRY_DISABLED=1
COPY packages packages
COPY apps/web apps/web
RUN npm run build -w @saige/web

FROM node:${NODE_VERSION}-alpine AS runtime
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app
RUN addgroup -S -g 10001 saige && adduser -S -u 10001 -G saige saige
COPY --from=builder --chown=saige:saige /repo/apps/web/.next/standalone ./
COPY --from=builder --chown=saige:saige /repo/apps/web/.next/static ./apps/web/.next/static
USER saige
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
