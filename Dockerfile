# syntax=docker/dockerfile:1
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /opt/dagster/app

ENV DAGSTER_HOME=/opt/dagster/dagster_home
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Layer 1: install dependencies (cached until pyproject.toml changes)
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    mkdir -p etl && touch etl/__init__.py \
    && uv pip install --system -e .

# Layer 2: swap in real pipeline code (overlaid by bind-mount in local compose)
COPY etl ./etl

COPY dagster/dagster.yaml "${DAGSTER_HOME}/dagster.yaml"
COPY workspace.yaml ./workspace.yaml
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
