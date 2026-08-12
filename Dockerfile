FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/dagster/app

ENV DAGSTER_HOME=/opt/dagster/dagster_home
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Layer 1: install dependencies (cached until pyproject.toml changes)
COPY pyproject.toml ./
RUN mkdir -p my_pipelines && touch my_pipelines/__init__.py \
    && pip install --no-cache-dir -e .

# Layer 2: swap in real pipeline code (fast rebuild on code-only changes)
COPY my_pipelines ./my_pipelines

COPY dagster/dagster.yaml "${DAGSTER_HOME}/dagster.yaml"
COPY workspace.yaml ./workspace.yaml
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
