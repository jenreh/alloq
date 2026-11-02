# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.14-slim-bookworm
ARG UV_VERSION=0.12.19
ARG BUN_VERSION=1.4.0
# Image digests (multi-arch index); update them together with the versions.
ARG PYTHON_DIGEST=sha256:516b51cb9db2ef061e465c803e50f64361b82cefd91e525b889b967b83e83527
ARG UV_DIGEST=sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424
ARG BUN_DIGEST=sha256:5ff609364c049b54eb0ff560ec96319729a972078ef2c755d758f0c6ef89c2d6

FROM ghcr.io/astral-sh/uv:${UV_VERSION}@${UV_DIGEST} AS uv
FROM oven/bun:${BUN_VERSION}@${BUN_DIGEST} AS bun

# ────────────────────────────  Stage 1 ─ Builder  ────────────────────────────
FROM python:${PYTHON_VERSION}@${PYTHON_DIGEST} AS builder

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
FROM python:${PYTHON_VERSION}@${PYTHON_DIGEST} AS final

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
