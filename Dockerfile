# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.14-slim-bookworm
ARG UV_VERSION=0.12.19
ARG BUN_VERSION=1.4.0

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM oven/bun:${BUN_VERSION} AS bun

# ────────────────────────────  Stage 1 ─ Builder  ────────────────────────────
FROM python:${PYTHON_VERSION} AS builder

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_CACHE_DIR=/root/.cache/uv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /reflexapp

COPY pyproject.toml uv.lock README.md .python-version ./
COPY components ./components

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --all-extras

COPY alembic.ini start.sh rxconfig.py ./
COPY configuration ./configuration
COPY assets ./assets
COPY alembic ./alembic
COPY app ./app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --all-extras \
    && chmod +x start.sh

# ───────────────────────────  Stage 2 ─ Runtime  ────────────────────────────
FROM python:${PYTHON_VERSION} AS final

# Frontend and backend share one port (reflex run --env prod --single-port).
ARG PORT=8080
ARG API_URL

RUN groupadd --system --gid 1000 alloq \
    && useradd --system --uid 1000 --gid alloq --create-home alloq

# Reflex uses a bun >= its pinned minimum from PATH instead of downloading one.
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
COPY --from=builder --chown=alloq:alloq /reflexapp /reflexapp

ENV PATH="/reflexapp/.venv/bin:${PATH}" \
    PORT=${PORT} \
    REFLEX_FRONTEND_PORT=${PORT} \
    REFLEX_BACKEND_PORT=${PORT} \
    REFLEX_API_URL=${API_URL:-http://localhost:$PORT}

WORKDIR /reflexapp
USER alloq

EXPOSE ${PORT}

CMD ["./start.sh"]
