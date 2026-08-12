FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/dagster/app

ENV DAGSTER_HOME=/opt/dagster/dagster_home
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml ./
COPY my_pipelines ./my_pipelines
RUN pip install --no-cache-dir .

COPY dagster/dagster.yaml "${DAGSTER_HOME}/dagster.yaml"
COPY workspace.yaml ./workspace.yaml
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
