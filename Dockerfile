# syntax=docker/dockerfile:1
FROM python:3.11.13-slim@sha256:9bffe4353b925a1656688797ebc68f9c525e79b1d377a764d232182a519eeec4 AS app

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1 /uv /usr/local/bin/uv

WORKDIR /opt/dagster/app

ENV DAGSTER_HOME=/opt/dagster/dagster_home
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/opt/dagster/app/.venv/bin:${PATH}"

# Layer 1: install the exact dependency graph from uv.lock.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Layer 2: pipeline code. Changes here need scripts/deploy.sh (make deploy).
COPY etl ./etl

COPY dagster/dagster.yaml "${DAGSTER_HOME}/dagster.yaml"
COPY workspace.yaml ./workspace.yaml
COPY scripts/dagster_ops.py ./dagster_ops.py
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# Test image (make test): app + dev dependencies + tests/. Never deployed; compose
# files build `target: app` explicitly because the last stage is the default.
FROM app AS test
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project
COPY tests ./tests
