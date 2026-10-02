# syntax=docker/dockerfile:1.7
# Saige Vault API image (also used for running migrations).
# Build context: repository root.

ARG PYTHON_VERSION=3.12

FROM ghcr.io/astral-sh/uv:0.12 AS uv

FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src

# Dependency layer: only lockfile + manifests, so source edits don't bust it.
COPY pyproject.toml uv.lock ./
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/ai/pyproject.toml services/ai/pyproject.toml
COPY services/worker/pyproject.toml services/worker/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package saige-api

COPY services/api services/api
COPY services/ai services/ai
COPY services/worker/pyproject.toml services/worker/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package saige-api

FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN groupadd --system --gid 10001 saige \
 && useradd --system --uid 10001 --gid saige --no-create-home --shell /usr/sbin/nologin saige
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# Migrations + Alembic config (paths mirror the repository layout).
COPY database/migrations database/migrations
COPY services/api/alembic.ini services/api/alembic.ini
COPY --chmod=0755 infrastructure/docker/api-entrypoint.sh /usr/local/bin/saige-api-entrypoint
USER saige
EXPOSE 8000
CMD ["saige-api-entrypoint"]
